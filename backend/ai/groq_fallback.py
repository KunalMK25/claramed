"""
Groq model fallback.

Groq retires models from time to time (llama-3.1-8b-instant is one), and a
retired model answers "model_not_found". Instead of failing, every Groq call
is built from an ordered list of models: if one is gone, the next is tried.
"""
from typing import Iterable, List, Optional

from langchain_groq import ChatGroq

from backend.core.config import settings

# Text models, best first. The configured model is always tried first.
TEXT_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

# Models that can read an image, best first.
VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]


def model_order(configured: Optional[str], defaults: Iterable[str]) -> List[str]:
    """The configured model first, then the defaults, without repeats."""
    ordered: List[str] = []
    for name in [configured, *defaults]:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _chat(model: str, temperature: float, max_tokens: int, api_key: Optional[str]) -> ChatGroq:
    kwargs = {"model": model, "temperature": temperature, "max_tokens": max_tokens}
    if api_key:
        kwargs["api_key"] = api_key
    return ChatGroq(**kwargs)


def build_llm(models: List[str], temperature: float, max_tokens: int, api_key: Optional[str] = None):
    """A chat model that moves on to the next model when one is unavailable."""
    primary, *rest = [_chat(m, temperature, max_tokens, api_key) for m in models]
    return primary.with_fallbacks(rest) if rest else primary


def text_llm(temperature: float = 0.2, max_tokens: int = 1024, api_key: Optional[str] = None):
    return build_llm(model_order(settings.GROQ_MODEL, TEXT_MODELS), temperature, max_tokens, api_key)


def vision_llm(temperature: float = 0.2, max_tokens: int = 1024, api_key: Optional[str] = None):
    return build_llm(model_order(settings.GROQ_VISION_MODEL, VISION_MODELS), temperature, max_tokens, api_key)
