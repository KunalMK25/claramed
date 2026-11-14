"""
End to end: POST /analyze -> real Celery tasks (eager) -> finalizer -> signed callback -> JeevaCare stub.
Only the file download and the heavy model/LLM calls are faked.
"""
import io
import uuid

import pytest
from PIL import Image

from backend.models.analysis import AnalysisStatus, MedicalAnalysis
from backend.models.audit import AuditEvent
from backend.services import integration_service
from backend.services.document_service import DocumentService
from backend.services.radiology_service import RadiologyService
from backend.services.url_fetcher import FetchedFile, FetchError
from backend.workers import callbacks
from tests.support.jeevacare_stub import JeevaCareStub

FAKE_RESULT = {
    "modality": "chest_xray", "model_name": "densenet121-res224-all", "disclaimer": "Not a diagnosis.",
    "processing_duration_seconds": 0.1,
    "findings": [{"label": "Edema", "model_score": 0.83}, {"label": "Atelectasis", "model_score": 0.12}],
}
JEEVACARE_BODY = {"radiologyId": "rad-1", "imageUrl": "https://res.cloudinary.com/x/a.png",
                  "patientId": "JV-PAT-1", "metadata": {"modality": "chest_xray"}}


def _png_bytes():
    buf = io.BytesIO()
    Image.new("L", (224, 224), 128).save(buf, "PNG")
    return buf.getvalue()


def _stored_files(storage_dir):
    return [p for p in storage_dir.rglob("*") if p.is_file()]


@pytest.fixture
def world(monkeypatch, make_client, auth_headers):
    reg = make_client(callback_auth_token="jv-token")
    stub = JeevaCareStub(reg.webhook_secret, expected_token="jv-token")
    monkeypatch.setattr(callbacks, "_http_client", stub.client)
    monkeypatch.setattr(callbacks, "backoff_seconds", lambda n: 0)       # eager retries run instantly
    monkeypatch.setattr(RadiologyService, "analyze_chest_xray", lambda self, path: FAKE_RESULT)
    monkeypatch.setattr(DocumentService, "extract_text_from_pdf",
                        lambda self, path: {"text": "Hemoglobin 9.1 g/dL", "requires_ocr": False})
    monkeypatch.setattr(DocumentService, "explain_report",
                        lambda self, report_text, language: {"explanation": "Your hemoglobin is low.", "model": "stub"})
    monkeypatch.setattr(DocumentService, "extract_structured_findings",
                        lambda self, report_text, language: [{"test": "Hemoglobin", "value": 9.1}])
    monkeypatch.setattr(integration_service, "fetch_file", lambda url, **kw: FetchedFile(
        content=_png_bytes() if kw["kind"] == "radiology" else b"%PDF-1.4\n" + b"0" * 32,
        kind_detected="png" if kw["kind"] == "radiology" else "pdf",
        extension=".png" if kw["kind"] == "radiology" else ".pdf"))
    return reg, stub, auth_headers(reg.api_key)


def test_radiology_end_to_end_with_jeevacare_documented_request(world, api_client, db, storage_dir):
    reg, stub, headers = world
    r = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY)
    assert r.status_code == 202
    job = r.json()["jobId"]

    assert len(stub.received) == 1
    cb = stub.received[0]
    assert cb["jobId"] == job and cb["status"] == "completed" and cb["radiologyId"] == "rad-1"
    assert cb["results"]["findings"][0] == {"label": "Edema", "score": 0.83}
    assert cb["results"]["confidence"] == 0.83 and cb["error"] is None
    assert _stored_files(storage_dir) == []                       # source file deleted after analysis

    analysis = db.get(MedicalAnalysis, uuid.UUID(job))
    db.refresh(analysis)
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.delivery_status == "delivered" and analysis.results_expire_at is not None

    status = api_client.get(f"/api/v1/status/{job}", headers=headers).json()
    assert status["status"] == "completed" and status["deliveryStatus"] == "delivered"
    assert status["results"] == cb["results"]
    actions = {e.action for e in db.query(AuditEvent).all()}
    assert {"analysis_submitted", "file_deleted", "callback_attempt"} <= actions


def test_document_end_to_end(world, api_client, storage_dir):
    _, stub, headers = world
    r = api_client.post("/api/v1/analyze", headers=headers, json={
        "documentId": "doc-7", "fileUrl": "https://res.cloudinary.com/x/r.pdf"})
    assert r.status_code == 202
    cb = stub.received[0]
    assert cb["documentId"] == "doc-7" and cb["status"] == "completed"
    assert cb["results"]["explanation"] == "Your hemoglobin is low."
    assert cb["results"]["findings"] == [{"test": "Hemoglobin", "value": 9.1}]
    assert _stored_files(storage_dir) == []


def test_worker_failure_sends_failed_callback_and_deletes_the_file(world, monkeypatch, api_client, storage_dir):
    _, stub, headers = world

    def boom(self, path):
        raise RuntimeError("model exploded: internal detail")
    monkeypatch.setattr(RadiologyService, "analyze_chest_xray", boom)
    api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY)
    assert stub.received and stub.received[-1]["status"] == "failed"
    assert stub.received[-1]["results"] is None
    assert "internal detail" not in str(stub.received[-1])
    assert _stored_files(storage_dir) == []


def test_receiver_outage_then_recovery_delivers_after_retries(world, api_client, db):
    _, stub, headers = world
    stub.fail_next = 2
    job = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY).json()["jobId"]
    assert len(stub.received) == 1 and stub.requests == 3
    analysis = db.get(MedicalAnalysis, uuid.UUID(job))
    db.refresh(analysis)
    assert analysis.delivery_status == "delivered" and analysis.delivery_attempts == 3


def test_receiver_down_for_good_is_marked_failed_but_results_stay_pollable(world, api_client, db):
    _, stub, headers = world
    stub.fail_next = 99
    job = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY).json()["jobId"]
    db.expire_all()   # the test shares one session with the API; production gives each request its own
    status = api_client.get(f"/api/v1/status/{job}", headers=headers).json()
    assert status["deliveryStatus"] == "failed"
    assert status["status"] == "completed" and status["results"]["findings"]     # polling still works


@pytest.mark.parametrize("code", ["host_not_allowed", "blocked_address", "too_large"])
def test_intake_rejections_surface_as_422_and_store_nothing(world, monkeypatch, api_client, db, storage_dir, code):
    _, stub, headers = world

    def reject(url, **kw):
        raise FetchError(code, "rejected")
    monkeypatch.setattr(integration_service, "fetch_file", reject)
    r = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY)
    assert r.status_code == 422 and r.json()["error"]["code"] == code
    assert db.query(MedicalAnalysis).count() == 0 and _stored_files(storage_dir) == []
    assert stub.received == []


def test_cross_client_isolation_and_anonymous_access(world, make_client, auth_headers, api_client):
    _, _, headers = world
    job = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY).json()["jobId"]
    other = make_client("other-hospital-system")
    assert api_client.get(f"/api/v1/status/{job}", headers=auth_headers(other.api_key)).status_code == 404
    assert api_client.get(f"/api/v1/status/{job}").status_code == 401
    assert api_client.post("/api/v1/analyze", json={}).status_code == 401


def test_resubmitting_a_completed_record_does_not_reprocess_or_resend(world, api_client):
    _, stub, headers = world
    first = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY).json()["jobId"]
    second = api_client.post("/api/v1/analyze", headers=headers, json=JEEVACARE_BODY).json()
    assert second["jobId"] == first and second["status"] == "completed"
    assert len(stub.received) == 1
