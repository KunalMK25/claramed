import pytest
"""Unit tests for the vision-LLM explainer used for non-chest X-rays."""
from PIL import Image

from backend.core.exceptions import ModelError
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


def test_failure_raises_with_the_real_reason_instead_of_inventing_text(tmp_path):
    with pytest.raises(ModelError) as caught:
        explain_other_xray(
            _png(tmp_path), language="English", llm=_FakeVisionLLM(error=RuntimeError("boom"))
        )
    assert "boom" in str(caught.value)


def test_blank_reply_raises(tmp_path):
    with pytest.raises(ModelError):
        explain_other_xray(_png(tmp_path), language="English", llm=_FakeVisionLLM(reply=" "))


def test_gemini_is_used_first_when_a_key_is_set(tmp_path, monkeypatch):
    from backend.services import xray_vision

    monkeypatch.setattr(xray_vision.settings, "GEMINI_API_KEY", "test-key", raising=False)
    sent = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "A fractured wrist."}]}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"], sent["json"], sent["headers"] = url, json, headers
        return _Resp()

    monkeypatch.setattr("httpx.post", fake_post)
    result = explain_other_xray(_png(tmp_path), language="English")

    assert result["generated_by"] == "gemini"
    assert "fractured wrist" in result["explanation"]
    assert sent["headers"]["x-goog-api-key"] == "test-key"
    assert "test-key" not in sent["url"]
    assert sent["json"]["contents"][0]["parts"][1]["inline_data"]["data"]
