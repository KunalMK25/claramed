"""
Turn an uploaded X-ray file (PNG, JPG, DICOM or PDF) into an image file the
radiology model can read.
"""
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from backend.core.exceptions import ValidationError

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf", ".dcm"}


def _pdf_to_png(path: Path, out_dir: Path) -> Path:
    try:
        from pdf2image import convert_from_path

        pages = convert_from_path(str(path), dpi=200, first_page=1, last_page=1)
        if not pages:
            raise ValueError("PDF has no pages")
        out = out_dir / f"{path.stem}_page1.png"
        pages[0].save(out, "PNG")
        return out
    except Exception as e:
        raise ValidationError(f"Could not read the PDF: {e}")


def _dicom_to_png(path: Path, out_dir: Path) -> Path:
    try:
        import pydicom

        ds = pydicom.dcmread(str(path))
        arr = ds.pixel_array.astype(np.float32)
        if arr.ndim == 3 and getattr(ds, "SamplesPerPixel", 1) == 1:
            arr = arr[0]  # multi-frame: first frame
        lo, hi = float(arr.min()), float(arr.max())
        arr = (arr - lo) / (hi - lo) if hi > lo else np.zeros_like(arr)
        if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
            arr = 1.0 - arr
        out = out_dir / f"{path.stem}.png"
        Image.fromarray((arr * 255).astype(np.uint8)).save(out, "PNG")
        return out
    except Exception as e:
        raise ValidationError(f"Could not read the DICOM file: {e}")


def prepare_image(path: Path, out_dir: Optional[Path] = None) -> Path:
    """
    Return a PNG/JPG path for the upload.

    PNG/JPG files are returned as is; PDFs (first page) and DICOM files are
    converted into ``out_dir`` (default: next to the input).
    """
    path = Path(path)
    if not path.exists():
        raise ValidationError(f"File not found: {path.name}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type: {suffix or 'none'}",
            details={"supported": sorted(SUPPORTED_EXTENSIONS)},
        )
    if suffix in IMAGE_EXTENSIONS:
        return path

    out_dir = Path(out_dir) if out_dir else path.parent
    return _pdf_to_png(path, out_dir) if suffix == ".pdf" else _dicom_to_png(path, out_dir)
