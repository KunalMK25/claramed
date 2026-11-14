"""
Patient-friendly explanation of chest X-ray AI findings.

The model only produces per-condition scores. This module turns them into a
structured, plain-English report:

* an overall verdict (no concerns / needs attention / inconclusive),
* each flagged finding explained in everyday words with a low/moderate/high level,
* what looked normal,
* next steps and questions to ask a doctor.

The structure is computed deterministically from the scores. An LLM (optional)
only rewrites that structure into friendly prose, so it cannot invent findings,
and a template version is used whenever the LLM is unavailable.
"""
import math
from typing import Any, Dict, List, Optional

from backend.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_THRESHOLD = 0.5

DISCLAIMER = (
    "This is an AI-generated explanation, not a radiologist's diagnosis. "
    "AI can miss problems or flag things that are not there, so please have "
    "a doctor review your X-ray."
)

# label (lowercase, spaces) -> (plain name, what it is in everyday words)
_PLAIN: Dict[str, tuple] = {
    "atelectasis": ("partially collapsed lung area",
                    "A small part of the lung has deflated a little, so it is not filling with air fully."),
    "consolidation": ("area of lung filled with fluid or material",
                      "Part of the lung looks solid instead of airy, often because of infection or fluid."),
    "infiltration": ("cloudy area in the lung",
                     "A hazy patch in the lung that can be caused by infection, inflammation or fluid."),
    "pneumothorax": ("collapsed lung (air outside the lung)",
                     "Air has leaked into the space around the lung, which can make part of it collapse."),
    "edema": ("fluid in the lungs",
              "Extra fluid in the lungs, which can make breathing harder."),
    "emphysema": ("emphysema (damaged air sacs)",
                  "Long-term damage to the lung's tiny air sacs, often linked to smoking."),
    "fibrosis": ("lung scarring",
                 "Scar-like stiffening of lung tissue, which can make the lungs less flexible."),
    "effusion": ("fluid around the lung",
                 "Fluid has collected in the space between the lung and the chest wall."),
    "pneumonia": ("pneumonia (lung infection)",
                  "An infection that inflames the lungs and can fill the air sacs with fluid."),
    "pleural thickening": ("thickening of the lung lining",
                           "The thin lining around the lung looks thicker than usual, often from old inflammation."),
    "cardiomegaly": ("enlarged heart",
                     "The heart looks bigger than expected on the X-ray."),
    "nodule": ("small lung spot (nodule)",
               "A small round spot in the lung. Most are harmless, but a doctor should check them."),
    "mass": ("larger lung lump (mass)",
             "A larger lump in the lung that needs a doctor's follow-up to find out what it is."),
    "hernia": ("hernia near the diaphragm",
               "Part of the stomach or other tissue may be pushing up through the diaphragm."),
    "lung lesion": ("lung lesion",
                    "An area in the lung that looks different from the tissue around it."),
    "fracture": ("rib fracture (broken rib)",
                 "A possible crack or break in one of the ribs."),
    "lung opacity": ("hazy area in the lung",
                     "A part of the lung that looks whiter or hazier than normal."),
    "enlarged cardiomediastinum": ("widened central chest area",
                                   "The space in the middle of the chest, around the heart, looks wider than usual."),
}

# Findings where a moderate/high flag should prompt urgent medical attention.
_URGENT_LABELS = {"pneumothorax"}


def _key(label: str) -> str:
    return label.replace("_", " ").strip().lower()


def _valid_threshold(value: Any) -> float:
    try:
        t = float(value)
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD
    if math.isnan(t) or t <= 0:
        return DEFAULT_THRESHOLD
    return min(t, 0.99)


def _level(score: float, threshold: float) -> str:
    """How far above its threshold the score is: low / moderate / high."""
    strength = (score - threshold) / (1 - threshold)
    if strength < 0.25:
        return "low"
    if strength < 0.7:
        return "moderate"
    return "high"


def build_summary(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn raw model scores into a structured, patient-oriented summary."""
    if not findings:
        return {"overall": "inconclusive", "flagged": [], "not_flagged": [], "urgent": False}

    flagged: List[Dict[str, Any]] = []
    not_flagged: List[str] = []
    for f in findings:
        label = f.get("label", "Unknown")
        score = float(f.get("model_score", 0.0))
        threshold = _valid_threshold(f.get("threshold", DEFAULT_THRESHOLD))
        plain_name, what_it_is = _PLAIN.get(
            _key(label),
            (label.replace("_", " "), "The AI noticed a pattern it associates with this condition."),
        )
        if score >= threshold:
            flagged.append({
                "label": label,
                "plain_name": plain_name,
                "what_it_is": what_it_is,
                "level": _level(score, threshold),
                "_score": score,
            })
        else:
            not_flagged.append(plain_name)

    flagged.sort(key=lambda x: x["_score"], reverse=True)
    for item in flagged:
        del item["_score"]  # raw scores are model internals, not patient-facing

    urgent = any(
        _key(i["label"]) in _URGENT_LABELS and i["level"] in ("moderate", "high")
        for i in flagged
    )
    return {
        "overall": "attention" if flagged else "no_concerns",
        "flagged": flagged,
        "not_flagged": not_flagged,
        "urgent": urgent,
    }


def render_template_explanation(summary: Dict[str, Any]) -> str:
    """Plain-English Markdown report built without an LLM."""
    overall = summary["overall"]
    lines: List[str] = ["## What your X-ray shows", ""]

    if overall == "inconclusive":
        lines += [
            "We could not read any results from this X-ray, so we can't say whether "
            "everything is fine. Please show the image to a doctor.",
        ]
    elif overall == "no_concerns":
        lines += [
            "**Good news: no issues were flagged.** The AI checked this chest X-ray for "
            "common problems and nothing concerning stood out.",
        ]
    else:
        n = len(summary["flagged"])
        lines += [
            f"The AI flagged **{n} area{'s' if n != 1 else ''}** that a doctor should look at. "
            "A flag does not mean you definitely have the condition.",
        ]
        if summary["urgent"]:
            lines += [
                "",
                "**One finding can be serious. Please contact a doctor or emergency "
                "services right away, especially if you have chest pain or trouble breathing.**",
            ]
        lines += ["", "## What was flagged", ""]
        for item in summary["flagged"]:
            lines.append(
                f"- **{item['plain_name'].capitalize()}** ({item['level']} level of concern): "
                f"{item['what_it_is']}"
            )

    if summary["not_flagged"] and overall != "inconclusive":
        lines += ["", "## What looks normal", "",
                  "The AI did not flag: " + ", ".join(summary["not_flagged"]) + "."]

    lines += ["", "## Next steps", ""]
    if overall == "no_concerns":
        lines += [
            "- Keep this result for your records.",
            "- A clear AI result does not rule out every problem. If you feel unwell, "
            "see a doctor anyway.",
        ]
    else:
        lines += [
            "- Share this X-ray with a doctor or radiologist for a proper review.",
            "- Seek urgent care if you have chest pain, trouble breathing, or coughing blood.",
        ]

    lines += ["", "## Questions to ask your doctor", "",
              "- Does the X-ray show anything that needs treatment or more tests?",
              "- Do I need a follow-up X-ray or scan, and when?",
              "- Are there symptoms I should watch for?", "",
              f"_{DISCLAIMER}_"]
    return "\n".join(lines)


def _summary_for_prompt(summary: Dict[str, Any]) -> str:
    """Factual text handed to the LLM. No raw scores, nothing to invent from."""
    lines = [f"Overall result: {summary['overall']}",
             f"Urgent attention needed: {'yes' if summary['urgent'] else 'no'}"]
    if summary["flagged"]:
        lines.append("Flagged findings (strongest first):")
        for i in summary["flagged"]:
            lines.append(f"- {i['plain_name']} [{i['level']} level]: {i['what_it_is']}")
    else:
        lines.append("Flagged findings: none")
    if summary["not_flagged"]:
        lines.append("Checked and not flagged: " + ", ".join(summary["not_flagged"]))
    return "\n".join(lines)


def ensure_disclaimer(text: str) -> str:
    """Append the standard disclaimer unless the text already carries one."""
    if "not a radiologist" in text.lower():
        return text
    return f"{text.rstrip()}\n\n_{DISCLAIMER}_"


def get_explanation_chain():
    """LLM chain that narrates a summary, or None when the LLM is unavailable."""
    try:
        from backend.ai.llm_provider import get_llm_provider
        from backend.ai.prompts import RADIOLOGY_EXPLANATION_PROMPT

        return get_llm_provider().create_chain(RADIOLOGY_EXPLANATION_PROMPT)
    except Exception as e:  # missing key, bad config, import error
        logger.warning(f"Radiology LLM unavailable, using template: {e}")
        return None


def explain_chest_findings(
    findings: List[Dict[str, Any]],
    language: str = "English",
    chain: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build the structured summary and a plain-English explanation of it."""
    summary = build_summary(findings)

    if chain is not None:
        try:
            text = chain.invoke({
                "summary_text": _summary_for_prompt(summary),
                "language": language,
            })
            if text and text.strip():
                return {"summary": summary, "explanation": ensure_disclaimer(text.strip()),
                        "generated_by": "llm"}
            logger.warning("Radiology LLM returned an empty explanation, using template")
        except Exception as e:
            logger.error(f"Radiology LLM explanation failed, using template: {e}")

    return {"summary": summary, "explanation": render_template_explanation(summary),
            "generated_by": "template"}
