from pathlib import Path

import pytest

from backend.core.exceptions import ProcessingError, ValidationError
from streamlit_app.radiology_flow import MAX_UPLOAD_BYTES, UploadError, analyze_upload

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
RESULT = {
    "findings": [{"label": "Edema", "model_score": 0.2}, {"label": "Pneumothorax", "model_score": 0.9},
                 {"label": "Atelectasis", "model_score": 0.5}, {"label": "Mass", "model_score": 0.1}],
    "disclaimer": "Not a diagnosis.", "model_name": "densenet121-res224-all", "processing_duration_seconds": 1.5,
}


class FakeService:
    def __init__(self, result=RESULT, error=None):
        self.result, self.error, self.paths = result, error, []

    def analyze_chest_xray(self, path: Path):
        self.paths.append(path)
        assert path.exists() and path.read_bytes()          # the model really gets a readable file
        if self.error:
            raise self.error
        return self.result


def test_findings_are_ranked_highest_first_and_top_picks_the_leaders():
    out = analyze_upload(PNG, lambda: FakeService())
    assert [f.label for f in out.findings] == ["Pneumothorax", "Atelectasis", "Edema", "Mass"]
    assert [f.label for f in out.top(2)] == ["Pneumothorax", "Atelectasis"]
    assert out.top()[0].score == 0.9
    assert out.disclaimer == "Not a diagnosis." and out.model_name == "densenet121-res224-all" and out.seconds == 1.5


def test_png_and_jpeg_are_accepted_and_the_temp_file_gets_the_right_suffix():
    svc = FakeService()
    analyze_upload(PNG, lambda: svc)
    analyze_upload(JPEG, lambda: svc)
    assert [p.suffix for p in svc.paths] == [".png", ".jpg"]


def test_the_temp_file_is_deleted_after_success():
    svc = FakeService()
    analyze_upload(PNG, lambda: svc)
    assert not svc.paths[0].exists()


@pytest.mark.parametrize("error", [ValidationError("bad"), ProcessingError("bad"), RuntimeError("boom")])
def test_the_temp_file_is_deleted_when_the_analysis_fails(error):
    svc = FakeService(error=error)
    with pytest.raises(UploadError):
        analyze_upload(PNG, lambda: svc)
    assert not svc.paths[0].exists()


def test_empty_oversize_and_non_image_uploads_are_rejected_without_even_loading_the_model():
    svc, loads = FakeService(), []

    def factory():
        loads.append(1)                            # loading the model is expensive: never do it for a bad upload
        return svc

    for data, code in [(b"", "empty"), (PNG + b"0" * MAX_UPLOAD_BYTES, "too_large"),
                       (b"%PDF-1.4 not an image", "not_an_image"), (b"<html>hi</html>", "not_an_image")]:
        with pytest.raises(UploadError) as e:
            analyze_upload(data, factory)
        assert e.value.code == code
    assert svc.paths == [] and loads == []


def test_the_service_decides_what_a_bad_image_is_and_users_get_a_generic_message():
    with pytest.raises(UploadError) as e:
        analyze_upload(PNG, lambda: FakeService(error=ValidationError("Invalid image file: /tmp/secret-name.png truncated")))
    assert e.value.code == "invalid_image" and "secret-name" not in e.value.message


def test_unexpected_errors_never_leak_details():
    with pytest.raises(UploadError) as e:
        analyze_upload(PNG, lambda: FakeService(error=RuntimeError("patient-ABC.png exploded")))
    assert e.value.code == "analysis_failed" and "patient-ABC" not in e.value.message
