"""Unit tests for the vision-LLM explainer used for non-chest X-rays."""
from PIL import Image

from backend.services.xray_vision import explain_other_xray


class _FakeVisionLLM:
    def __init__(self, reply="## Summary\nA hand X-ray.", error=None):
        self.reply, self.error, self.messages = reply, error, None

    def invoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error

        class R:  # mimics a LangChain AIMessage
            content = self.reply

        return R()


def _png(tmp_path):
    p = tmp_path / "hand.png"
    Image.new("L", (16, 16), 128).save(p)
    return p


def test_image_is_sent_as_data_url_with_requested_language(tmp_path):
    llm = _FakeVisionLLM()
    explain_other_xray(_png(tmp_path), language="Hindi", llm=llm)
    content = llm.messages[-1].content
    kinds = {part["type"] for part in content}
    assert kinds == {"text", "image_url"}
    image_part = next(p for p in content if p["type"] == "image_url")
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    text = " ".join(p["text"] for p in content if p["type"] == "text")
    assert "Hindi" in text


def test_result_has_explanation_disclaimer_and_vision_source(tmp_path):
    result = explain_other_xray(_png(tmp_path), language="English", llm=_FakeVisionLLM())
    assert result["generated_by"] == "vision_llm"
    assert "A hand X-ray." in result["explanation"]
    assert "not a radiologist" in result["explanation"].lower()
    assert result["modality"] == "xray_other"


def test_llm_failure_returns_safe_unavailable_message(tmp_path):
    result = explain_other_xray(
        _png(tmp_path), language="English", llm=_FakeVisionLLM(error=RuntimeError("boom"))
    )
    assert result["generated_by"] == "unavailable"
    assert "could not" in result["explanation"].lower()
    assert "doctor" in result["explanation"].lower()


def test_blank_reply_returns_unavailable(tmp_path):
    result = explain_other_xray(_png(tmp_path), language="English", llm=_FakeVisionLLM(reply=" "))
    assert result["generated_by"] == "unavailable"
