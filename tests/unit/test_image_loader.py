"""Unit tests for turning PNG/JPG/PDF/DICOM uploads into a model-ready image."""
import numpy as np
import pytest
from PIL import Image

from backend.core.exceptions import ValidationError
from backend.services.image_loader import prepare_image


def _gray_image(size=(64, 48)):
    arr = (np.random.RandomState(0).rand(size[1], size[0]) * 255).astype("uint8")
    return Image.fromarray(arr)


def test_png_is_returned_unchanged(tmp_path):
    p = tmp_path / "x.png"
    _gray_image().save(p)
    assert prepare_image(p, tmp_path) == p


def test_jpeg_is_returned_unchanged(tmp_path):
    p = tmp_path / "x.jpeg"
    _gray_image().save(p)
    assert prepare_image(p, tmp_path) == p


def test_pdf_first_page_is_rendered_to_png(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _gray_image().convert("RGB").save(pdf, "PDF")
    out = prepare_image(pdf, tmp_path)
    assert out.suffix == ".png" and out != pdf
    with Image.open(out) as img:
        assert img.size[0] > 0 and img.size[1] > 0


def test_corrupt_pdf_raises_validation_error(tmp_path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a pdf")
    with pytest.raises(ValidationError):
        prepare_image(pdf, tmp_path)


def test_dicom_is_converted_to_png(tmp_path):
    pydicom = pytest.importorskip("pydicom")
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    arr = (np.random.RandomState(1).rand(32, 32) * 4000).astype("uint16")
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(str(tmp_path / "s.dcm"), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.Rows, ds.Columns = arr.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.PixelData = arr.tobytes()
    ds.save_as(str(tmp_path / "s.dcm"), write_like_original=False)

    out = prepare_image(tmp_path / "s.dcm", tmp_path)
    assert out.suffix == ".png"
    with Image.open(out) as img:
        assert img.size == (32, 32)


def test_unsupported_extension_is_rejected(tmp_path):
    p = tmp_path / "x.gif"
    _gray_image().save(p)
    with pytest.raises(ValidationError):
        prepare_image(p, tmp_path)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        prepare_image(tmp_path / "nope.png", tmp_path)
