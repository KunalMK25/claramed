"""Validate an uploaded X-ray (PNG, JPEG, DICOM or PDF), analyse it and explain it in plain English. No Streamlit imports."""
import logging
import tempfile
import time
from typing import Optional
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.core.config import settings
import re

from backend.core.exceptions import ModelError, ValidationError
from backend.services.image_loader import prepare_image
from backend.services.radiology_explainer import DISCLAIMER, explain_chest_findings
from backend.services.url_fetcher import FetchError, detect_file

logger = logging.getLogger(__name__)

# One limit for the whole app: the same setting the radiology service itself enforces.
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


_SECRET = re.compile(r"(AIza[0-9A-Za-z_\-]{10,}|gsk_[0-9A-Za-z]{10,}|[Bb]earer\s+\S+)")


def _safe_reason(error: Exception, limit: int = 900) -> str:
    """The provider's own error text, with anything key-shaped removed and cut short."""
    return _SECRET.sub("[hidden]", str(error)).strip()[:limit]


class UploadError(Exception):
    """A problem the user can act on. `message` is safe to show: it never contains file names or contents."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Finding:
    label: str
    score: float


@dataclass
class RadiologyOutcome:
    findings: list[Finding]          # every finding, highest score first (empty for non-chest X-rays)
    disclaimer: str
    model_name: str
    seconds: float
    explanation: str = ""            # plain-English Markdown report: this is what the patient reads
    summary: Optional[dict] = None   # structured verdict behind the explanation (chest only)
    generated_by: str = "template"   # "llm" | "template" | "vision_llm" | "unavailable"

    def top(self, n: int = 3) -> list[Finding]:
        return self.findings[:n]


BODY_PARTS = ("auto", "chest", "other")


def _detect_extension(data: bytes) -> str:
    """File extension by content, never by file name. Raises FetchError for anything unsupported."""
    try:
        _, extension = detect_file(data, "radiology")
        return extension
    except FetchError:
        if data.startswith(b"%PDF-"):
            return ".pdf"
        if data[128:132] == b"DICM":
            return ".dcm"
        raise


def _default_vision(path: Path, language: str) -> dict:
    from backend.services.xray_vision import explain_other_xray

    return explain_other_xray(path, language)


def _default_detect(path: Path) -> Optional[str]:
    from backend.services.xray_vision import detect_body_part

    return detect_body_part(path)


def analyze_upload(
    data: bytes,
    get_service: Callable[[], object],
    language: str = "English",
    body_part: str = "chest",
    chain_factory: Optional[Callable[[], object]] = None,
    vision: Callable[[Path, str], dict] = _default_vision,
    detect: Callable[[Path], Optional[str]] = _default_detect,
) -> RadiologyOutcome:
    """
    Validate `data` as a PNG/JPEG/DICOM/PDF X-ray, analyse it and explain the result in plain English.
    The bytes touch disk only in temp files, always removed.

    `body_part="auto"` first asks a vision model which kind of X-ray this is (the image leaves the server
    for that question), then continues as "chest" or "other". `body_part="chest"` runs the chest model from `get_service()` (an object with
    `analyze_chest_xray(path) -> dict`); `"other"` asks the vision LLM instead (the image leaves the server).
    The service is only requested AFTER the upload passed validation, because loading the model is
    expensive and a bad file should never trigger it. `chain_factory` builds the LLM that words the
    explanation; without it, or if it fails, a built-in template is used.
    """
    if body_part not in BODY_PARTS:
        raise UploadError("bad_body_part", "Choose either a chest X-ray or another body part.")
    if not data:
        raise UploadError("empty", "The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError("too_large", f"The file is larger than {settings.MAX_UPLOAD_SIZE_MB} MB.")
    try:
        extension = _detect_extension(data)
    except FetchError:
        raise UploadError("not_an_image", "This does not look like a PNG, JPEG, DICOM or PDF file.") from None

    path = image = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp.write(data)
            path = Path(tmp.name)
        image = prepare_image(path)                              # PDF / DICOM -> PNG; PNG / JPEG unchanged
        if body_part == "auto":
            # When the body part cannot be told, the general reader still describes any X-ray,
            # so the person always gets an analysis rather than a request to choose.
            body_part = detect(image)
            if body_part != "chest":
                body_part = "other"
        if body_part == "other":
            started = time.perf_counter()
            result = vision(image, language)
            return RadiologyOutcome([], DISCLAIMER, result["model_name"], time.perf_counter() - started,
                                    result["explanation"], None, result["generated_by"])
        result = get_service().analyze_chest_xray(image)
        explained = explain_chest_findings(
            result["findings"], language, chain=chain_factory() if chain_factory else None)
    except UploadError:
        raise
    except ValidationError:
        raise UploadError("invalid_image", "This image could not be read. Try another file.") from None
    except ModelError as e:
        logger.exception("radiology analysis failed")
        raise UploadError("analysis_failed", f"The analysis failed. {_safe_reason(e)}") from None
    except Exception:
        logger.exception("radiology analysis failed")           # server log only; no file name or content
        raise UploadError("analysis_failed", "The analysis failed. Please try again.") from None
    finally:
        for temp in (path, image):
            if temp is not None:
                temp.unlink(missing_ok=True)

    findings = sorted(
        (Finding(f["label"], float(f["model_score"])) for f in result["findings"]),
        key=lambda f: f.score, reverse=True,
    )
    return RadiologyOutcome(findings, result["disclaimer"], result["model_name"],
                            float(result["processing_duration_seconds"]),
                            explained["explanation"], explained["summary"], explained["generated_by"])
