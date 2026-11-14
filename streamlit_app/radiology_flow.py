"""Validate an uploaded chest X-ray and run the radiology model on it. No Streamlit imports."""
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.core.config import settings
from backend.core.exceptions import ValidationError
from backend.services.url_fetcher import FetchError, detect_file

logger = logging.getLogger(__name__)

# One limit for the whole app: the same setting the radiology service itself enforces.
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


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
    findings: list[Finding]          # every finding, highest score first
    disclaimer: str
    model_name: str
    seconds: float

    def top(self, n: int = 3) -> list[Finding]:
        return self.findings[:n]


def analyze_upload(data: bytes, get_service: Callable[[], object]) -> RadiologyOutcome:
    """
    Validate `data` as a PNG/JPEG and analyse it. The bytes touch disk only in one temp file, always removed.

    `get_service` returns an object with `analyze_chest_xray(path) -> dict`. It is called only AFTER the upload
    passed validation, because loading the model is expensive and a bad file should never trigger it.
    """
    if not data:
        raise UploadError("empty", "The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError("too_large", f"The file is larger than {settings.MAX_UPLOAD_SIZE_MB} MB.")
    try:
        _, extension = detect_file(data, "radiology")           # by content, never by file name
    except FetchError:
        raise UploadError("not_an_image", "This does not look like a PNG or JPEG image.") from None

    path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp.write(data)
            path = Path(tmp.name)
        result = get_service().analyze_chest_xray(path)
    except ValidationError:
        raise UploadError("invalid_image", "This image could not be read. Try another PNG or JPEG.") from None
    except Exception:
        logger.exception("radiology analysis failed")           # server log only; no file name or content
        raise UploadError("analysis_failed", "The analysis failed. Please try again.") from None
    finally:
        if path is not None:
            path.unlink(missing_ok=True)

    findings = sorted(
        (Finding(f["label"], float(f["model_score"])) for f in result["findings"]),
        key=lambda f: f.score, reverse=True,
    )
    return RadiologyOutcome(findings, result["disclaimer"], result["model_name"],
                            float(result["processing_duration_seconds"]))
