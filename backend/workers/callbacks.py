"""
Lifecycle of an integration analysis after it ends.

    worker finishes (or is swept as stale)
        -> finalize_integration_analysis : delete source files, set retention, queue the callback
        -> deliver_callback              : signed POST to the client's webhook, retried with backoff
        -> purge_expired_results         : hourly, removes results past RESULT_RETENTION_DAYS
        -> sweep_stale_jobs_task         : every 10 min, fails jobs a dead worker left behind

Legacy (non-integration) analyses have no external_record_id and are never touched here.
"""
import json
import time
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.signing import sign_payload
from backend.database.connection import get_db_context
from backend.models.analysis import AnalysisStatus, DeliveryStatus, MedicalAnalysis
from backend.models.document import UploadedDocument
from backend.models.integration_client import IntegrationClient
from backend.services.audit_service import record_event
from backend.services.integration_service import build_results_payload, id_field
from backend.services.storage_service import StorageService
from backend.workers.celery_app import celery_app

logger = get_logger(__name__)

PURGE_BATCH = 500  # per run; the task is hourly, so a larger backlog drains over several runs


def backoff_seconds(retries_so_far: int) -> int:
    """Delay before the next attempt: base * 2^n (120, 240, 480, 960 s with the defaults)."""
    return settings.CALLBACK_BACKOFF_BASE_SECONDS * (2 ** retries_so_far)


def build_callback_body(db: Session, analysis: MedicalAnalysis) -> bytes:
    """Canonical JSON (sorted keys, no spaces). Failures carry a generic code, never internals."""
    failed = analysis.status == AnalysisStatus.FAILED
    payload = {
        "jobId": str(analysis.id),
        "status": "failed" if failed else "completed",
        id_field(analysis): analysis.external_record_id,
        "results": None if failed else build_results_payload(db, analysis),
        "error": {"code": "analysis_failed"} if failed else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _http_client() -> httpx.Client:
    return httpx.Client(timeout=settings.CALLBACK_TIMEOUT_SECONDS, follow_redirects=False)


def _deliverable_client(db: Session, analysis: MedicalAnalysis) -> IntegrationClient | None:
    client = db.get(IntegrationClient, analysis.requesting_client_id) if analysis.requesting_client_id else None
    if client is None or not client.active or not client.webhook_url:
        return None
    return client


def _post_callback(http: httpx.Client, client: IntegrationClient, body: bytes) -> str | None:
    """Send one signed callback. Returns None on a 2xx, otherwise a short error description."""
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "X-ClaraMed-Timestamp": str(timestamp),
        "X-ClaraMed-Signature": sign_payload(client.webhook_secret, timestamp, body),
    }
    if client.callback_auth_token:
        headers["Authorization"] = f"Bearer {client.callback_auth_token}"
    try:
        response = http.post(client.webhook_url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        return type(exc).__name__
    return None if 200 <= response.status_code < 300 else f"http {response.status_code}"


def run_delivery_attempt(db: Session, analysis_id: str, attempt_index: int, http: httpx.Client) -> str:
    """One delivery attempt. Returns "delivered", "retry" or "failed" (no more attempts / undeliverable)."""
    analysis = db.query(MedicalAnalysis).filter(MedicalAnalysis.id == UUID(analysis_id)).first()
    if analysis is None:
        return "failed"
    if analysis.delivery_status == DeliveryStatus.DELIVERED:
        return "delivered"
    client = _deliverable_client(db, analysis)
    if client is None:
        analysis.delivery_status = DeliveryStatus.SKIPPED
        db.commit()
        return "failed"

    client_id, client_name = client.id, client.client_name
    error = _post_callback(http, client, build_callback_body(db, analysis))

    analysis.delivery_attempts = (analysis.delivery_attempts or 0) + 1
    analysis.delivery_last_error = error
    if error is None:
        analysis.delivery_status = DeliveryStatus.DELIVERED
        analysis.callback_delivered_at = datetime.utcnow()
        outcome = "delivered"
    elif attempt_index + 1 >= settings.CALLBACK_MAX_ATTEMPTS:
        analysis.delivery_status = DeliveryStatus.FAILED
        outcome = "failed"
    else:
        outcome = "retry"
    record_event(db, action="callback_attempt", resource_type="analysis", resource_id=analysis_id,
                 outcome="success" if error is None else "failure", client_id=client_id,
                 client_name=client_name, error=error, metadata={"attempt": attempt_index + 1}, commit=False)
    db.commit()  # delivery state and its audit row land together
    return outcome


@celery_app.task(bind=True, max_retries=settings.CALLBACK_MAX_ATTEMPTS - 1)
def deliver_callback(self, analysis_id: str):
    with get_db_context() as db, _http_client() as http:
        outcome = run_delivery_attempt(db, analysis_id, self.request.retries, http)
    if outcome == "retry":
        raise self.retry(countdown=backoff_seconds(self.request.retries))
    return outcome


def _remove_stored_files(db: Session, analysis_ids: list) -> int:
    """Delete the stored files of these analyses. A missing or undeletable file is logged, never fatal."""
    keys = [k for (k,) in db.query(UploadedDocument.storage_key)
            .filter(UploadedDocument.analysis_id.in_(analysis_ids))]
    storage = StorageService()
    for key in keys:
        try:
            storage.delete_file(key)
        except Exception as exc:
            logger.warning("stored file delete failed", error=type(exc).__name__)
    return len(keys)


def finalize_integration_analysis(db: Session, analysis_id: str, enqueue=None) -> bool:
    """
    Delete the stored source files, start the retention clock and queue the callback.
    Returns False (doing nothing) for unknown or legacy analyses and ones already finalized.
    """
    analysis = db.query(MedicalAnalysis).filter(MedicalAnalysis.id == UUID(analysis_id)).first()
    if not analysis or analysis.external_record_id is None or analysis.results_expire_at is not None:
        return False

    deleted = _remove_stored_files(db, [analysis.id])
    if deleted:
        record_event(db, action="file_deleted", resource_type="analysis", resource_id=analysis_id,
                     outcome="success", client_id=analysis.requesting_client_id,
                     metadata={"count": deleted}, commit=False)

    analysis.results_expire_at = datetime.utcnow() + timedelta(days=settings.RESULT_RETENTION_DAYS)
    if _deliverable_client(db, analysis) is None:
        analysis.delivery_status = DeliveryStatus.SKIPPED  # still pollable via /status
        db.commit()
        return True
    analysis.delivery_status = DeliveryStatus.PENDING
    db.commit()  # committed before the callback is queued, so the worker sees the final state
    (enqueue or deliver_callback.delay)(analysis_id)
    return True


def purge_expired(db: Session, now: datetime | None = None) -> int:
    """Delete analyses (and their results/findings/documents) past their retention window."""
    now = now or datetime.utcnow()
    expired = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.results_expire_at.isnot(None),
        MedicalAnalysis.results_expire_at < now,
    ).limit(PURGE_BATCH).all()
    if not expired:
        return 0
    _remove_stored_files(db, [a.id for a in expired])  # normally already gone; belt and braces
    for analysis in expired:
        db.delete(analysis)  # cascades to results, documents, findings
    record_event(db, action="results_purged", resource_type="analysis", resource_id=None,
                 outcome="success", metadata={"count": len(expired)}, commit=False)
    db.commit()
    logger.info("purged expired results", count=len(expired))
    return len(expired)


def sweep_stale_jobs(db: Session, now: datetime | None = None) -> int:
    """Fail integration jobs that a dead worker left queued/processing, then finalize them."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(seconds=settings.STALE_JOB_SECONDS)
    stale = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.external_record_id.isnot(None),
        MedicalAnalysis.status.in_([AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]),
        MedicalAnalysis.results_expire_at.is_(None),
        MedicalAnalysis.created_at < cutoff,
    ).all()
    for analysis in stale:
        analysis_id, client_id = str(analysis.id), analysis.requesting_client_id
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = "stale: worker did not finish"
        analysis.processing_completed_at = now
        record_event(db, action="stale_job_failed", resource_type="analysis", resource_id=analysis_id,
                     outcome="failure", client_id=client_id, commit=False)
        db.commit()  # FAILED must be committed before finalize runs
        finalize_integration_analysis(db, analysis_id)
    return len(stale)


@celery_app.task
def purge_expired_results() -> int:
    with get_db_context() as db:
        return purge_expired(db)


@celery_app.task
def sweep_stale_jobs_task() -> int:
    with get_db_context() as db:
        return sweep_stale_jobs(db)
