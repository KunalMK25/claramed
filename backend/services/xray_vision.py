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


def _encode_image(path: Path) -> str:
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
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode()}"


def _default_llm():
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.GROQ_VISION_MODEL,
        temperature=settings.GROQ_TEMPERATURE,
        max_tokens=settings.GROQ_MAX_TOKENS,
        api_key=settings.GROQ_API_KEY,
    )


_UNAVAILABLE = (
    "## What your X-ray shows\n\n"
    "We could not analyze this X-ray automatically right now. This does not mean "
    "anything is wrong.\n\n"
    "## Next steps\n\n"
    "- Please show the X-ray to a doctor or radiologist, who can review it properly.\n"
)


def explain_other_xray(
    image_path: Path,
    language: str = "English",
    llm: Optional[Any] = None,
) -> Dict[str, Any]:
    """Describe a non-chest X-ray in plain English."""
    base = {"modality": "xray_other", "summary": None, "model_name": settings.GROQ_VISION_MODEL}
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = llm or _default_llm()
        messages = [
            SystemMessage(content=SYSTEM_PROMPT.format(language=language)),
            HumanMessage(content=[
                {"type": "text", "text": f"Please explain this X-ray to me in {language}."},
                {"type": "image_url", "image_url": {"url": _encode_image(Path(image_path))}},
            ]),
        ]
        reply = llm.invoke(messages)
        text = (getattr(reply, "content", reply) or "").strip()
        if text:
            return {**base, "generated_by": "vision_llm", "explanation": ensure_disclaimer(text)}
        logger.warning("Vision LLM returned an empty explanation")
    except Exception as e:
        logger.error(f"Vision X-ray explanation failed: {e}", exc_info=True)

    return {**base, "generated_by": "unavailable", "explanation": ensure_disclaimer(_UNAVAILABLE)}
