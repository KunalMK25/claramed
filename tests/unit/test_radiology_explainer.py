"""Unit tests for the patient-friendly radiology explainer."""
from backend.services.radiology_explainer import (
    build_summary,
    explain_chest_findings,
    render_template_explanation,
)


def _findings(**scores):
    return [{"label": k.replace("_", " ") if k == "Lung_Lesion" else k, "model_score": v}
            for k, v in scores.items()]


HEALTHY = _findings(Fracture=0.05, Pneumonia=0.10, Cardiomegaly=0.20, Pneumothorax=0.02)


# ---- build_summary -------------------------------------------------------

def test_healthy_scan_has_no_flagged_findings_and_no_concerns_verdict():
    summary = build_summary(HEALTHY)
    assert summary["overall"] == "no_concerns"
    assert summary["flagged"] == []
    assert summary["urgent"] is False


def test_healthy_scan_lists_what_looks_normal_in_plain_words():
    summary = build_summary(HEALTHY)
    normal = " ".join(summary["not_flagged"]).lower()
    assert "rib fracture" in normal
    assert "pneumonia" in normal


def test_score_above_default_threshold_is_flagged_with_plain_description():
    summary = build_summary(_findings(Fracture=0.9, Pneumonia=0.1))
    assert summary["overall"] == "attention"
    [flag] = summary["flagged"]
    assert flag["label"] == "Fracture"
    assert "rib" in flag["plain_name"].lower()
    assert flag["what_it_is"]  # non-empty everyday explanation


def test_per_finding_threshold_overrides_default():
    findings = [{"label": "Nodule", "model_score": 0.6, "threshold": 0.3}]
    assert [f["label"] for f in build_summary(findings)["flagged"]] == ["Nodule"]
    findings = [{"label": "Nodule", "model_score": 0.6, "threshold": 0.8}]
    assert build_summary(findings)["flagged"] == []


def test_levels_increase_with_score():
    levels = [
        build_summary(_findings(Mass=s))["flagged"][0]["level"]
        for s in (0.65, 0.8, 0.97)
    ]
    assert levels == ["low", "moderate", "high"]


# ---- borderline: scores barely over the threshold are not real flags ------

def test_scores_barely_over_threshold_are_borderline_not_flagged():
    summary = build_summary(_findings(Fibrosis=0.5, Pleural_Thickening=0.52, Mass=0.1))
    assert summary["flagged"] == []
    assert [b["label"] for b in summary["borderline"]] == ["Pleural_Thickening", "Fibrosis"]
    assert summary["overall"] == "borderline"
    assert summary["urgent"] is False


def test_borderline_items_are_not_listed_as_normal():
    summary = build_summary(_findings(Fibrosis=0.5, Mass=0.1))
    assert all("scarring" not in n for n in summary["not_flagged"])


def test_real_flags_win_over_borderline_in_the_verdict():
    summary = build_summary(_findings(Fibrosis=0.5, Fracture=0.95))
    assert summary["overall"] == "attention"
    assert [f["label"] for f in summary["flagged"]] == ["Fracture"]
    assert [b["label"] for b in summary["borderline"]] == ["Fibrosis"]


def test_healthy_scan_has_empty_borderline_list():
    assert build_summary(HEALTHY)["borderline"] == []


def test_borderline_template_is_gentle_and_does_not_claim_no_issues():
    text = render_template_explanation(build_summary(_findings(Fibrosis=0.5))).lower()
    assert "no issues" not in text
    assert "faint" in text and "lung scarring" in text
    assert "mention" in text and "doctor" in text
    assert "0.5" not in text


def test_borderline_items_are_given_to_the_llm_as_uncertain():
    chain = _FakeChain(reply="ok")
    explain_chest_findings(_findings(Fibrosis=0.5), language="English", chain=chain)
    text = chain.calls[0]["summary_text"].lower()
    assert "borderline" in text and "lung scarring" in text


def test_flagged_sorted_strongest_first():
    summary = build_summary(_findings(Mass=0.6, Fracture=0.95, Nodule=0.7))
    assert [f["label"] for f in summary["flagged"]] == ["Fracture", "Nodule", "Mass"]


def test_strong_pneumothorax_marks_result_urgent():
    assert build_summary(_findings(Pneumothorax=0.95))["urgent"] is True


def test_weak_pneumothorax_is_not_urgent():
    assert build_summary(_findings(Pneumothorax=0.55))["urgent"] is False


def test_unknown_label_is_handled_gracefully():
    summary = build_summary([{"label": "Weird_Thing", "model_score": 0.9}])
    [flag] = summary["flagged"]
    assert flag["plain_name"] == "Weird Thing"
    assert flag["what_it_is"]


def test_nan_threshold_falls_back_to_default():
    findings = [{"label": "Mass", "model_score": 0.9, "threshold": float("nan")}]
    assert len(build_summary(findings)["flagged"]) == 1


def test_empty_findings_is_not_reported_as_healthy():
    summary = build_summary([])
    assert summary["overall"] == "inconclusive"


# ---- template explanation ------------------------------------------------

def test_template_for_healthy_scan_clearly_says_no_issues():
    text = render_template_explanation(build_summary(HEALTHY)).lower()
    assert "no issues" in text or "nothing concerning" in text
    assert "doctor" in text


def test_template_for_flagged_scan_explains_finding_and_next_steps():
    text = render_template_explanation(build_summary(_findings(Fracture=0.95))).lower()
    assert "rib fracture" in text
    assert "next steps" in text
    assert "questions to ask" in text


def test_template_never_shows_raw_model_scores():
    text = render_template_explanation(build_summary(_findings(Fracture=0.9137)))
    assert "0.91" not in text and "0.9137" not in text


def test_template_for_urgent_result_mentions_prompt_care():
    text = render_template_explanation(build_summary(_findings(Pneumothorax=0.95))).lower()
    assert "urgent" in text or "right away" in text


def test_template_for_inconclusive_result_does_not_claim_healthy():
    text = render_template_explanation(build_summary([])).lower()
    assert "no issues" not in text
    assert "could not" in text


# ---- explain_chest_findings (LLM narration with fallback) ----------------

class _FakeChain:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def invoke(self, variables):
        self.calls.append(variables)
        if self.error:
            raise self.error
        return self.reply


def test_llm_text_is_used_when_available_and_disclaimer_is_ensured():
    chain = _FakeChain(reply="## Summary\nAll looks fine.")
    result = explain_chest_findings(HEALTHY, language="English", chain=chain)
    assert result["generated_by"] == "llm"
    assert "All looks fine." in result["explanation"]
    assert "not a radiologist" in result["explanation"].lower()


def test_llm_is_grounded_on_structured_summary_not_raw_scores():
    chain = _FakeChain(reply="ok")
    explain_chest_findings(_findings(Fracture=0.9137), language="Hindi", chain=chain)
    [variables] = chain.calls
    assert variables["language"] == "Hindi"
    assert "rib fracture" in variables["summary_text"].lower()
    assert "0.9137" not in variables["summary_text"]


def test_llm_failure_falls_back_to_template():
    chain = _FakeChain(error=RuntimeError("groq down"))
    result = explain_chest_findings(HEALTHY, language="English", chain=chain)
    assert result["generated_by"] == "template"
    assert result["explanation"]


def test_blank_llm_reply_falls_back_to_template():
    result = explain_chest_findings(HEALTHY, language="English", chain=_FakeChain(reply="  "))
    assert result["generated_by"] == "template"


def test_no_chain_uses_template():
    result = explain_chest_findings(HEALTHY, language="English", chain=None)
    assert result["generated_by"] == "template"
    assert result["summary"]["overall"] == "no_concerns"
