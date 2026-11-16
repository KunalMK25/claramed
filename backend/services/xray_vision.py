"""
Plain-English explanation of non-chest X-rays (hand, leg, spine, ...) using a
vision-capable LLM.

The chest model cannot read other body parts, so these images are sent to the
configured Groq vision model. This is a general description only, never a
diagnosis, and it is clearly labelled as such. Note that the image leaves
this server and goes to Groq.
"""
import base64
import io
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

from backend.core.config import settings
from backend.core.exceptions import ModelError
from backend.core.logging import get_logger
from backend.services.radiology_explainer import ensure_disclaimer

logger = get_logger(__name__)

MAX_DIMENSION = 1024
MAX_PNG_BYTES = 3 * 1024 * 1024  # Groq limits base64 image requests to ~4 MB

SYSTEM_PROMPT = """You are a careful medical assistant explaining an X-ray image to a patient with no medical training.

Write in simple, plain language, in short sentences, in {language}. Use exactly these Markdown sections:
## What your X-ray shows
Say which body part this appears to be and describe what is visible. If you see nothing unusual, clearly say you do not see any obvious problems.
## What looks normal
## Anything that may need attention
Mention possible fractures, breaks, joint problems, unusual shadows or anything else that looks wrong, in everyday words. Say "possible" and never state a firm diagnosis. Write "None noticed" if nothing stands out.
## Next steps
## Questions to ask your doctor

Rules: you are not a radiologist; this is not a diagnosis; image quality or angle can hide problems; always recommend a doctor reviews the X-ray. If the image is not an X-ray or is unreadable, say so plainly and do not guess."""


def _image_parts(path: Path):
    """The image as (mime type, base64 text), shrunk to fit provider limits."""
    with Image.open(path) as img:
        img = img.convert("L") if img.mode not in ("L", "RGB") else img
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        mime = "image/png"
        if buf.tell() > MAX_PNG_BYTES:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=85)
            mime = "image/jpeg"
    return mime, base64.b64encode(buf.getvalue()).decode()


def _encode_image(path: Path) -> str:
    mime, data = _image_parts(path)
    return f"data:{mime};base64,{data}"


def _default_llm():
    from backend.ai.groq_fallback import vision_llm

    return vision_llm(
        temperature=settings.GROQ_TEMPERATURE,
        max_tokens=settings.GROQ_MAX_TOKENS,
        api_key=settings.GROQ_API_KEY,
    )


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_LIST_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.5-flash"]  # last resort if the model list cannot be read
_NOT_FOR_IMAGES = ("lite", "tts", "image", "live", "embedding", "audio", "robotics", "computer", "learnlm")


def _version(name: str):
    """gemini-3.1-flash -> (3, 1); used to put the newest model first."""
    import re

    return tuple(int(n) for n in re.findall(r"\d+", name.split("flash")[0])) or (0,)


def _current_gemini_models(api_key: str):
    """Flash models the key can use right now, newest stable first. Google retires models often."""
    import httpx

    resp = httpx.get(GEMINI_LIST_URL, headers={"x-goog-api-key": api_key}, params={"pageSize": 200}, timeout=20)
    resp.raise_for_status()
    names = [
        m["name"].removeprefix("models/")
        for m in resp.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    flash = [
        n for n in names
        if n.startswith("gemini-") and "flash" in n and not any(bad in n for bad in _NOT_FOR_IMAGES)
    ]
    # Stable before preview/experimental, then newest version first.
    flash.sort(key=lambda n: (("preview" in n or "exp" in n), tuple(-v for v in _version(n)), n))
    return flash


_working_gemini_model: Optional[str] = None  # the model that last worked; tried first next time


def _gemini_describe(image_path: Path, language: str) -> Optional[str]:
    """Describe the image with Google Gemini. Returns None when no key is set."""
    return _gemini_generate(
        image_path,
        system=SYSTEM_PROMPT.format(language=language),
        user_text=f"Please explain this X-ray to me in {language}.",
        max_tokens=2048,
    )


def _gemini_generate(image_path: Path, system: str, user_text: str, max_tokens: int) -> Optional[str]:
    """One Gemini call with an image. Returns None when no key is set."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return None

    import httpx

    mime, data = _image_parts(image_path)
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"text": user_text},
                {"inline_data": {"mime_type": mime, "data": data}},
            ],
        }],
        "generationConfig": {"temperature": settings.GROQ_TEMPERATURE, "maxOutputTokens": max_tokens},
    }
    try:
        available = _cached_gemini_models(api_key)
    except Exception as e:
        logger.warning(f"Could not list Gemini models: {e}")
        available = []
    global _working_gemini_model
    last: Optional[Exception] = None
    order = _model_order(
        _working_gemini_model,
        [*available[:3], *GEMINI_MODELS, getattr(settings, "GEMINI_VISION_MODEL", None)],
    )
    for model in order:
        try:
            resp = httpx.post(
                GEMINI_URL.format(model=model),
                json=body,
                headers={"x-goog-api-key": api_key},
                timeout=40,
            )
            resp.raise_for_status()
            parts = resp.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                _working_gemini_model = model
                return text
            last = ValueError(f"{model} returned no text")
        except Exception as e:  # try the next model
            logger.warning(f"Gemini model {model} failed: {e}")
            last = e
    raise last or RuntimeError("Gemini returned nothing")


_MODEL_LIST_TTL = 600  # seconds; Google changes its models rarely
_model_list_cache = {"at": 0.0, "models": []}


def _cached_gemini_models(api_key: str):
    import time

    if time.time() - _model_list_cache["at"] > _MODEL_LIST_TTL:
        _model_list_cache["models"] = _current_gemini_models(api_key)
        _model_list_cache["at"] = time.time()
    return _model_list_cache["models"]


BODY_PART_PROMPT = (
    "You look at medical images. Reply with exactly one word. "
    "Reply CHEST if the image is an X-ray of the chest or thorax (lungs, ribs, heart, collar bones). "
    "Reply OTHER for an X-ray of any other body part (hand, wrist, arm, leg, foot, spine, skull, pelvis, abdomen...) "
    "or if it is not an X-ray."
)


def detect_body_part(image_path: Path, llm: Optional[Any] = None) -> Optional[str]:
    """
    Which kind of X-ray is this? "chest", "other", or None when it cannot be told
    (no image provider available, or an unclear answer). Never raises.
    """
    image_path = Path(image_path)
    try:
        if llm is not None:
            reply = _groq_ask(image_path, BODY_PART_PROMPT, "Which body part is this?", llm)
        elif getattr(settings, "GEMINI_API_KEY", None):
            reply = _gemini_generate(image_path, BODY_PART_PROMPT, "Which body part is this?", max_tokens=256)
        else:
            reply = _groq_ask(image_path, BODY_PART_PROMPT, "Which body part is this?", _default_llm())
    except Exception as e:
        logger.warning(f"Body part detection failed: {e}")
        return None
    word = (reply or "").strip().lower()
    if word.startswith("chest"):
        return "chest"
    if word.startswith("other"):
        return "other"
    return None


def _model_order(configured: Optional[str], defaults):
    from backend.ai.groq_fallback import model_order

    return model_order(configured, defaults)


def _groq_describe(image_path: Path, language: str, llm: Any) -> str:
    return _groq_ask(
        image_path, SYSTEM_PROMPT.format(language=language), f"Please explain this X-ray to me in {language}.", llm
    )


def _groq_ask(image_path: Path, system: str, user_text: str, llm: Any) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=[
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": _encode_image(image_path)}},
        ]),
    ]
    reply = llm.invoke(messages)
    return (getattr(reply, "content", reply) or "").strip()


def explain_other_xray(
    image_path: Path,
    language: str = "English",
    llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Describe any X-ray (hand, leg, spine, skull, ...) in plain English.

    The image is read by a vision model: Gemini when a key is configured, then
    Groq. If every provider fails this raises, with the real reason, instead of
    returning a made-up or empty explanation.
    """
    image_path = Path(image_path)
    providers = []
    if llm is not None:
        providers.append(("vision_llm", settings.GROQ_VISION_MODEL, lambda: _groq_describe(image_path, language, llm)))
    else:
        if getattr(settings, "GEMINI_API_KEY", None):
            providers.append(("gemini", "gemini", lambda: _gemini_describe(image_path, language)))
        providers.append(("vision_llm", settings.GROQ_VISION_MODEL, lambda: _groq_describe(image_path, language, _default_llm())))

    errors = []
    for source, model_name, run in providers:
        try:
            text = run()
        except Exception as e:
            logger.error(f"X-ray analysis via {source} failed: {e}", exc_info=True)
            errors.append(f"{source}: {e}")
            continue
        if text:
            return {
                "modality": "xray_other",
                "summary": None,
                "model_name": model_name,
                "generated_by": source,
                "explanation": ensure_disclaimer(text),
            }
        errors.append(f"{source}: empty reply")

    raise ModelError(
        "The X-ray could not be read by the image model. " + " | ".join(errors),
        model_name=settings.GROQ_VISION_MODEL,
    )
