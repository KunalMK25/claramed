"""
Radiology report orchestration.

Upload -> (PDF/DICOM to image) -> chest model or vision LLM -> plain-English
explanation -> database rows. Shared by the upload endpoint and the Celery task
so both behave identically.
"""
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

from backend.core.exceptions import ValidationError
from backend.models.analysis import AnalysisStatus, AnalysisType
from backend.models.radiology import RadiologyFinding
from backend.models.result import AnalysisResult, ResultType
from backend.services.image_loader import prepare_image
from backend.services.radiology_explainer import (
    DISCLAIMER,
    explain_chest_findings,
    get_explanation_chain,
)
from backend.services.xray_vision import explain_other_xray

BODY_PARTS = ("chest", "other")


def _analyze_chest(image_path: Path) -> Dict[str, Any]:
    # Imported lazily: pulls in torch, which the other paths don't need.
    from backend.services.radiology_service import RadiologyService

    return RadiologyService().analyze_chest_xray(image_path)


def build_report(
    file_path: Path,
    body_part: str = "chest",
    language: str = "English",
    workdir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Analyze an uploaded X-ray and explain it in plain English.

    ``body_part``: "chest" runs the chest X-ray model; "other" sends the image to
    a vision LLM for a general description (the chest model can't read other
    body parts).
    """
    if body_part not in BODY_PARTS:
        raise ValidationError(
            f"Unsupported body part: {body_part}", details={"supported": list(BODY_PARTS)}
        )

    file_path = Path(file_path)
    image = prepare_image(file_path, workdir)
    try:
        if body_part == "other":
            started = perf_counter()
            report = explain_other_xray(image, language)
            report["findings"] = []
            report["processing_duration_seconds"] = perf_counter() - started
            report["disclaimer"] = DISCLAIMER
            return report

        analysis = _analyze_chest(image)
        explained = explain_chest_findings(
            analysis["findings"], language, chain=get_explanation_chain()
        )
        return {**analysis, **explained}
    finally:
        if image != file_path:
            image.unlink(missing_ok=True)  # converted PDF/DICOM temp image


def save_report(db, analysis, report: Dict[str, Any]) -> None:
    """Add the report's rows to the session and complete the analysis (caller commits)."""
    for f in report["findings"]:
        db.add(RadiologyFinding(
            analysis_id=analysis.id,
            finding_label=f["label"],
            model_score=f["model_score"],
            model_name=report["model_name"],
            model_version=report.get("model_version", "pretrained"),
            modality=report["modality"],
        ))

    if report["findings"]:
        db.add(AnalysisResult(
            analysis_id=analysis.id,
            result_type=ResultType.RADIOLOGY_INFERENCE,
            content={
                "modality": report["modality"],
                "model_name": report["model_name"],
                "findings": report["findings"],
                "disclaimer": report.get("disclaimer", DISCLAIMER),
            },
            model_name=report["model_name"],
        ))

    db.add(AnalysisResult(
        analysis_id=analysis.id,
        result_type=ResultType.EXPLANATION,
        content={
            "explanation": report["explanation"],
            "summary": report.get("summary"),
            "generated_by": report["generated_by"],
        },
        model_name=report["model_name"],
    ))

    analysis.analysis_type = AnalysisType.XRAY
    analysis.status = AnalysisStatus.COMPLETED
    analysis.processing_completed_at = datetime.utcnow()
    analysis.processing_duration_seconds = str(report["processing_duration_seconds"])
