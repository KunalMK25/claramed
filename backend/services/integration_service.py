"""Submit/status logic for the client integration API."""
import hashlib
import tempfile
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.models.analysis import (
    AnalysisStatus, AnalysisType, DeliveryStatus, MedicalAnalysis, RecordKind,
)
from backend.models.document import DocumentType, UploadedDocument
from backend.models.integration_client import IntegrationClient
from backend.models.result import AnalysisResult, ResultType
from backend.schemas.integration import AnalyzeRequest
from backend.services.audit_service import record_event
from backend.services.storage_service import StorageService
from backend.services.url_fetcher import FetchedFile, fetch_file
from backend.workers.tasks import process_document_async, process_radiology_async

logger = get_logger(__name__)

_STATUS = {
    AnalysisStatus.PENDING: "queued",
    AnalysisStatus.PROCESSING: "processing",
    AnalysisStatus.COMPLETED: "completed",
    AnalysisStatus.FAILED: "failed",
}
_DOC_TYPE = {"png": DocumentType.IMAGE_PNG, "jpeg": DocumentType.IMAGE_JPEG, "pdf": DocumentType.PDF}
# kind -> (analysis type, storage prefix). The worker task is chosen in submit_analysis so tests can patch it.
_KIND = {
    RecordKind.RADIOLOGY: (AnalysisType.XRAY, "images"),
    RecordKind.DOCUMENT: (AnalysisType.DOCUMENT, "documents"),
}


class EnqueueError(Exception):
    """The task queue was unreachable; nothing was kept."""


def status_label(analysis: MedicalAnalysis) -> str:
    return _STATUS[analysis.status]


def id_field(analysis: MedicalAnalysis) -> str:
    """Name of the client's own id in request and callback bodies."""
    return "radiologyId" if analysis.external_record_kind == RecordKind.RADIOLOGY else "documentId"


def _find_existing(db: Session, client: IntegrationClient, kind: str, record_id: str):
    return db.query(MedicalAnalysis).filter_by(
        requesting_client_id=client.id, external_record_kind=kind, external_record_id=record_id
    ).first()


def _store_upload(storage: StorageService, analysis: MedicalAnalysis, req: AnalyzeRequest,
                  fetched: FetchedFile) -> UploadedDocument:
    """Persist the downloaded bytes with the storage service and describe them as an UploadedDocument."""
    filename = f"{req.record_id}{fetched.extension}"
    key = storage.generate_storage_key(
        analysis_id=str(analysis.id), filename=filename, prefix=_KIND[req.type][1],
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=fetched.extension) as tmp:
        tmp.write(fetched.content)
        tmp_path = Path(tmp.name)
    try:
        stored = storage.save_file(tmp_path, key)
    finally:
        tmp_path.unlink(missing_ok=True)
    return UploadedDocument(
        analysis_id=analysis.id,
        filename=key.split("/")[-1],
        original_filename=filename[:255],
        file_type=_DOC_TYPE[fetched.kind_detected],
        file_size=len(fetched.content),
        checksum=hashlib.sha256(fetched.content).hexdigest(),
        storage_key=key,
        storage_provider=stored["storage_provider"],
    )


def submit_analysis(db: Session, client: IntegrationClient, req: AnalyzeRequest) -> MedicalAnalysis:
    """
    Create (or return the existing) analysis for the client's record and queue it.

    Raises FetchError on intake failure and EnqueueError when the queue is down; in both cases nothing is
    persisted. A previous FAILED job for the same record is replaced; any other existing job is returned as is.
    """
    existing = _find_existing(db, client, req.type, req.record_id)
    if existing and existing.status != AnalysisStatus.FAILED:
        return existing

    # Fetch first: a bad URL must not destroy an old failed record.
    fetched = fetch_file(
        req.file_url,
        allowed_hosts=list(client.allowed_file_hosts or []),
        kind=req.type,
        max_bytes=settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024,
    )
    audit = dict(resource_type="analysis", client_id=client.id, client_name=client.client_name)

    if existing:
        replaced_id = str(existing.id)
        db.delete(existing)
        db.flush()  # the delete must hit the DB before the unique key is reused
        record_event(db, action="failed_job_replaced", resource_id=replaced_id, outcome="success",
                     commit=False, **audit)

    analysis = MedicalAnalysis(
        analysis_type=_KIND[req.type][0],
        status=AnalysisStatus.PENDING,
        input_data={"metadata": req.metadata},
        external_patient_reference=req.patient_ref,
        external_hospital_reference=req.hospitalRef,
        external_system=client.client_name,
        requesting_client_id=client.id,
        external_record_kind=req.type,
        external_record_id=req.record_id,
        delivery_status=DeliveryStatus.PENDING,
    )
    db.add(analysis)
    try:
        db.flush()
    except IntegrityError:
        # Another request created the same record between our lookup and now.
        db.rollback()
        return _find_existing(db, client, req.type, req.record_id)

    storage = StorageService()
    document = _store_upload(storage, analysis, req, fetched)
    db.add(document)
    db.flush()
    analysis_id, document_id, storage_key = str(analysis.id), str(document.id), document.storage_key
    db.commit()  # must be committed before a worker can see the rows

    task = process_radiology_async if req.type == RecordKind.RADIOLOGY else process_document_async
    try:
        task.delay(analysis_id, document_id)
    except Exception as exc:
        logger.error("enqueue failed", error=type(exc).__name__)
        try:
            storage.delete_file(storage_key)
        except Exception:
            logger.warning("could not remove stored file after enqueue failure")
        db.delete(analysis)
        db.commit()
        record_event(db, action="analysis_enqueue_failed", resource_id=analysis_id, outcome="failure", **audit)
        raise EnqueueError("task queue unavailable") from exc

    record_event(db, action="analysis_submitted", resource_id=analysis_id, outcome="success",
                 metadata={"kind": req.type}, **audit)
    return analysis


def _radiology_payload(result: AnalysisResult) -> dict:
    content = result.content
    findings = sorted(
        ({"label": f["label"], "score": float(f["model_score"])} for f in content.get("findings", [])),
        key=lambda f: f["score"], reverse=True,
    )
    top = ", ".join(f"{f['label']} ({f['score']:.2f})" for f in findings[:3]) or "no findings"
    return {
        "findings": findings,
        "summary": f"Highest model scores: {top}.",
        "confidence": findings[0]["score"] if findings else None,
        "disclaimer": content.get("disclaimer", ""),
    }


def build_results_payload(db: Session, analysis: MedicalAnalysis) -> dict | None:
    """The `results` object shared by /status and the callback. None unless the analysis completed."""
    if analysis.status != AnalysisStatus.COMPLETED:
        return None
    results = db.query(AnalysisResult).filter_by(analysis_id=analysis.id).all()
    by_type = {r.result_type: r for r in results}
    if ResultType.RADIOLOGY_INFERENCE in by_type:
        return _radiology_payload(by_type[ResultType.RADIOLOGY_INFERENCE])
    explanation = by_type.get(ResultType.EXPLANATION)
    structured = by_type.get(ResultType.STRUCTURED_FINDINGS)
    text = explanation.content.get("explanation", "") if explanation else ""
    return {
        "explanation": text,
        "findings": structured.content.get("findings", []) if structured else [],
        "summary": text[:500],
        "confidence": None,
        "disclaimer": "Educational information only; not a medical diagnosis.",
    }
