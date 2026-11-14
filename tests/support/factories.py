"""Shared test builders."""
from pathlib import Path

from backend.models.analysis import AnalysisStatus, AnalysisType, MedicalAnalysis
from backend.models.document import DocumentType, UploadedDocument


def make_analysis(db, client, record="rad-1", status=AnalysisStatus.COMPLETED, kind="radiology",
                  delivery_status="pending", expire=None, created_at=None, integration=True,
                  file_in: Path | None = None, content: bytes = b"\x89PNG", filename: str = "x.png",
                  file_type: DocumentType = DocumentType.IMAGE_PNG):
    """Create an analysis (optionally with a stored file under `file_in`). Returns (analysis, file_path)."""
    fields = dict(
        analysis_type=AnalysisType.XRAY if kind == "radiology" else AnalysisType.DOCUMENT,
        status=status,
        requesting_client_id=client.id,
        results_expire_at=expire,
    )
    if integration:
        fields.update(external_record_kind=kind, external_record_id=record, delivery_status=delivery_status)
    if created_at is not None:
        fields["created_at"] = created_at
    analysis = MedicalAnalysis(**fields)
    db.add(analysis)
    db.flush()
    path = None
    if file_in is not None:
        key = f"images/{analysis.id}/{filename}"
        path = file_in / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        db.add(UploadedDocument(
            analysis_id=analysis.id, filename=filename, original_filename=filename,
            file_type=file_type, file_size=len(content), checksum="c",
            storage_key=key, storage_provider="local",
        ))
    db.commit()
    return analysis, path
