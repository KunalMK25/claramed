import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from backend.ai import groq_fallback
from backend.ai.groq_fallback import TEXT_MODELS, build_llm, model_order


class RetiredModel(FakeListChatModel):
    """Behaves like a model Groq has retired."""

    def _generate(self, *args, **kwargs):
        raise RuntimeError("Error code: 404 - model_not_found: The model does not exist")


def test_configured_model_goes_first_without_repeats():
    order = model_order("llama-3.1-8b-instant", TEXT_MODELS)
    assert order[0] == "llama-3.1-8b-instant"
    assert len(order) == len(set(order))
    assert set(TEXT_MODELS) <= set(order)


def test_blank_configured_model_is_ignored():
    assert model_order(None, ["a", "b"]) == ["a", "b"]


def test_a_retired_model_falls_back_to_the_next(monkeypatch):
    fakes = {"gone": RetiredModel(responses=["x"]), "alive": FakeListChatModel(responses=["hello"])}
    monkeypatch.setattr(groq_fallback, "_chat", lambda model, *a, **k: fakes[model])

    llm = build_llm(["gone", "alive"], 0.2, 100)

    assert llm.invoke("hi").content == "hello"


def test_fails_when_every_model_is_gone(monkeypatch):
    monkeypatch.setattr(groq_fallback, "_chat", lambda model, *a, **k: RetiredModel(responses=["x"]))

    with pytest.raises(RuntimeError):
        build_llm(["a", "b"], 0.2, 100).invoke("hi")
