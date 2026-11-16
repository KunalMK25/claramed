import io
from pathlib import Path

import pytest
from PIL import Image

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
                       (b"<html>hi</html>", "not_an_image"), (b"plain text", "not_an_image")]:
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


# --- plain-English explanation, PDF/DICOM uploads and non-chest X-rays ---

def _pdf_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "gray").save(buf, "PDF")
    return buf.getvalue()


class FakeChain:
    def __init__(self, reply="## Summary\nLooks fine."):
        self.reply, self.calls = reply, []

    def invoke(self, variables):
        self.calls.append(variables)
        return self.reply


def test_outcome_carries_a_plain_english_explanation_without_an_llm():
    out = analyze_upload(PNG, lambda: FakeService())
    assert out.generated_by == "template"
    assert out.summary["overall"] == "attention"
    assert "collapsed lung" in out.explanation.lower()
    assert "0.9" not in out.explanation                 # raw model scores stay out of the explanation


def test_llm_chain_is_used_when_a_factory_is_given_with_the_chosen_language():
    chain = FakeChain()
    out = analyze_upload(PNG, lambda: FakeService(), language="Hindi", chain_factory=lambda: chain)
    assert out.generated_by == "llm" and "Looks fine." in out.explanation
    assert chain.calls[0]["language"] == "Hindi"


def test_pdf_upload_is_converted_to_an_image_before_the_model_sees_it():
    svc = FakeService()
    analyze_upload(_pdf_bytes(), lambda: svc)
    assert svc.paths[0].suffix == ".png"
    assert not svc.paths[0].exists()                    # converted temp image is cleaned up too


def test_a_broken_pdf_or_dicom_gets_the_generic_unreadable_message_and_skips_the_model():
    loads = []

    def factory():
        loads.append(1)
        return FakeService()

    for data in (b"%PDF-1.4 truncated", b"\0" * 128 + b"DICM" + b"junk"):
        with pytest.raises(UploadError) as e:
            analyze_upload(data, factory)
        assert e.value.code == "invalid_image"
    assert loads == []


def test_other_body_part_uses_the_vision_explainer_and_never_loads_the_chest_model():
    loads, seen = [], []

    def vision(path, language):
        seen.append((path.suffix, language))
        return {"modality": "xray_other", "summary": None, "model_name": "vision-model",
                "generated_by": "vision_llm", "explanation": "A hand X-ray."}

    out = analyze_upload(PNG, lambda: loads.append(1), language="Tamil", body_part="other", vision=vision)
    assert loads == [] and seen == [(".png", "Tamil")]
    assert out.findings == [] and out.explanation == "A hand X-ray." and out.generated_by == "vision_llm"
    assert out.model_name == "vision-model"


def test_unknown_body_part_is_rejected():
    with pytest.raises(UploadError) as e:
        analyze_upload(PNG, lambda: FakeService(), body_part="brain")
    assert e.value.code == "bad_body_part"


def test_provider_reason_is_shown_without_any_key():
    from streamlit_app.radiology_flow import _safe_reason

    text = _safe_reason(RuntimeError("403 key AIzaSyA1234567890abcdefghij and gsk_abcdefghij123456 Bearer tok123"))
    assert "AIza" not in text and "gsk_" not in text and "tok123" not in text
    assert "403" in text


def _vision_stub(seen):
    def vision(path, language):
        seen.append(path)
        return {"modality": "xray_other", "summary": None, "model_name": "vision-model",
                "generated_by": "vision_llm", "explanation": "A hand X-ray."}
    return vision


def test_auto_sends_a_hand_xray_to_the_vision_reader_and_never_loads_the_chest_model():
    loads, seen = [], []
    out = analyze_upload(PNG, lambda: loads.append(1), body_part="auto",
                         vision=_vision_stub(seen), detect=lambda path: "other")
    assert loads == [] and len(seen) == 1
    assert out.explanation == "A hand X-ray." and out.findings == []


def test_auto_sends_a_chest_xray_to_the_chest_model():
    seen = []
    out = analyze_upload(PNG, lambda: FakeService(), body_part="auto",
                         vision=_vision_stub(seen), detect=lambda path: "chest")
    assert seen == []
    assert out.findings  # produced by the chest model


def test_auto_asks_the_user_to_choose_when_the_body_part_cannot_be_told():
    with pytest.raises(UploadError) as e:
        analyze_upload(PNG, lambda: FakeService(), body_part="auto", detect=lambda path: None)
    assert e.value.code == "body_part_unknown"
    assert "choose" in e.value.message.lower()
