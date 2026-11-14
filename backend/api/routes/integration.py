"""Client integration API: submit a file for analysis and poll its status (see docs/CLARAMED_API.md)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import require_scope
from backend.core.config import settings
from backend.database.connection import get_db
from backend.models.analysis import MedicalAnalysis
from backend.models.integration_client import IntegrationClient
from backend.schemas.integration import AnalyzeRequest, AnalyzeResponse
from backend.services import integration_service as svc
from backend.services.url_fetcher import FetchError

router = APIRouter()


def _error(http_status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=http_status, content={"error": {"code": code, "message": message}})


# Plain `def` (not async): the file download is blocking and runs in FastAPI's threadpool.
@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
def analyze(
    req: AnalyzeRequest,
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_scope("analysis:create")),
):
    if not settings.CLARAMED_INTEGRATION_ENABLED:
        return _error(503, "integration_disabled", "The integration is temporarily disabled")
    try:
        analysis = svc.submit_analysis(db, client, req)
    except FetchError as exc:
        return _error(422, exc.code, exc.message)
    except svc.EnqueueError:
        return _error(503, "queue_unavailable", "Analysis queue is unavailable; retry shortly")
    return AnalyzeResponse(jobId=str(analysis.id), status=svc.status_label(analysis))


@router.get("/status/{job_id}")
def job_status(
    job_id: str,
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_scope("analysis:read")),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    analysis = db.query(MedicalAnalysis).filter_by(id=job_uuid, requesting_client_id=client.id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "jobId": str(analysis.id),
        "status": svc.status_label(analysis),
        svc.id_field(analysis): analysis.external_record_id,
        "results": svc.build_results_payload(db, analysis),
        "deliveryStatus": analysis.delivery_status,
    }
