"""Live smoke test: worker -> finalizer -> signed callback, with real Redis and a real Celery worker.

Prerequisites (separate terminals, same environment as the API):
    redis running, PostgreSQL migrated (alembic upgrade head)
    celery -A backend.workers.celery_app worker --pool=solo -l info

Run:  python scripts/jeevacare_smoke.py

What it does: registers a throwaway client whose webhook is a local HTTP receiver, stores a synthetic
X-ray with the real storage service, queues the real radiology task, and waits for the signed callback.
Then it checks the source file was deleted and cleans up after itself. File download from a URL is NOT
part of this script (that is covered by the unit tests); this proves the worker side under real Celery.
Prints PASS/FAIL and exits 0/1. Uses whatever DATABASE_URL / STORAGE_* the environment points at.
"""
import io
import json
import secrets
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from backend.core.security import generate_api_key, hash_api_key  # noqa: E402
from backend.core.signing import verify_signature  # noqa: E402
from backend.database.connection import get_db_context  # noqa: E402
from backend.models.analysis import AnalysisStatus, AnalysisType, MedicalAnalysis  # noqa: E402
from backend.models.document import DocumentType, UploadedDocument  # noqa: E402
from backend.models.integration_client import IntegrationClient  # noqa: E402
from backend.services.storage_service import StorageService  # noqa: E402
from backend.workers.tasks import process_radiology_async  # noqa: E402

TIMEOUT_SECONDS = 180
received: list[dict] = []
SECRET = secrets.token_hex(32)
TOKEN = secrets.token_hex(16)


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        ok = (
            self.headers.get("Authorization") == f"Bearer {TOKEN}"
            and verify_signature(SECRET, int(self.headers.get("X-ClaraMed-Timestamp", "0")), body,
                                 self.headers.get("X-ClaraMed-Signature", ""))
        )
        if ok:
            received.append(json.loads(body))
        self.send_response(200 if ok else 401)
        self.end_headers()

    def log_message(self, *args):
        pass


def main() -> int:
    server = HTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    name = f"smoke-{uuid.uuid4().hex[:8]}"
    storage = StorageService()
    analysis_id = key = None
    try:
        with get_db_context() as db:
            client = IntegrationClient(
                client_name=name, hashed_api_key=hash_api_key(generate_api_key()),
                scopes=["analysis:create", "analysis:read"], active=True,
                webhook_url=f"http://127.0.0.1:{port}/cb", webhook_secret=SECRET,
                callback_auth_token=TOKEN, allowed_file_hosts=["smoke.invalid"],
            )
            db.add(client)
            db.flush()
            analysis = MedicalAnalysis(
                analysis_type=AnalysisType.XRAY, status=AnalysisStatus.PENDING,
                requesting_client_id=client.id, external_system=name,
                external_record_kind="radiology", external_record_id="smoke-1", delivery_status="pending",
            )
            db.add(analysis)
            db.flush()
            buf = io.BytesIO()
            Image.effect_noise((512, 512), 40).convert("L").save(buf, "PNG")
            tmp = Path(f"/tmp/{name}.png")
            tmp.write_bytes(buf.getvalue())
            key = storage.generate_storage_key(str(analysis.id), "smoke.png", prefix="images")
            stored = storage.save_file(tmp, key)
            tmp.unlink(missing_ok=True)
            doc = UploadedDocument(
                analysis_id=analysis.id, filename="smoke.png", original_filename="smoke.png",
                file_type=DocumentType.IMAGE_PNG, file_size=len(buf.getvalue()), checksum="smoke",
                storage_key=key, storage_provider=stored["storage_provider"],
            )
            db.add(doc)
            db.flush()
            analysis_id, doc_id = str(analysis.id), str(doc.id)

        process_radiology_async.delay(analysis_id, doc_id)   # a REAL worker must pick this up
        print(f"queued job {analysis_id}; waiting up to {TIMEOUT_SECONDS}s for the signed callback...")

        deadline = time.time() + TIMEOUT_SECONDS
        while not received and time.time() < deadline:
            time.sleep(1)

        problems = []
        if not received:
            problems.append("no valid callback arrived (is a Celery worker running?)")
        else:
            cb = received[0]
            if cb.get("status") != "completed":
                problems.append(f"callback status was {cb.get('status')!r}")
            elif len(cb.get("results", {}).get("findings", [])) != 18:
                problems.append("callback did not carry the 18 model findings")
        with get_db_context() as db:
            row = db.get(MedicalAnalysis, uuid.UUID(analysis_id))
            if row.delivery_status != "delivered":
                problems.append(f"delivery_status is {row.delivery_status!r}, expected 'delivered'")
            if row.results_expire_at is None:
                problems.append("retention clock was not started")
        try:
            storage.get_file(key)
            problems.append("source file still exists after analysis")
        except Exception:
            pass  # expected: the finalizer deleted it

        print("PASS" if not problems else "FAIL: " + "; ".join(problems))
        return 0 if not problems else 1
    finally:
        server.shutdown()
        with get_db_context() as db:
            if analysis_id:
                row = db.get(MedicalAnalysis, uuid.UUID(analysis_id))
                if row:
                    db.delete(row)
            db.query(IntegrationClient).filter_by(client_name=name).delete()
        if key:
            try:
                storage.delete_file(key)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
