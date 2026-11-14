"""Unit tests for the upload -> explanation orchestration and persistence."""
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from backend.models.analysis import AnalysisStatus, AnalysisType
from backend.models.result import ResultType
from backend.models.radiology import RadiologyFinding
from backend.services import radiology_report
from backend.services.radiology_report import build_report, save_report


class _StubChestAnalyzer:
    def __init__(self, scores):
        self.scores, self.seen = scores, []

    def __call__(self, image_path):
        self.seen.append(image_path)
        return {
            "modality": "chest_xray",
            "model_name": "stub-model",
            "model_version": "pretrained",
            "findings": [{"label": k, "model_score": v} for k, v in self.scores.items()],
            "processing_duration_seconds": 0.5,
        }


@pytest.fixture
def png(tmp_path):
    p = tmp_path / "x.png"
    Image.fromarray((np.random.RandomState(0).rand(20, 20) * 255).astype("uint8")).save(p)
    return p


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(radiology_report, "get_explanation_chain", lambda: None)


def test_chest_report_contains_findings_and_plain_english_explanation(png, monkeypatch):
    monkeypatch.setattr(radiology_report, "_analyze_chest", _StubChestAnalyzer({"Fracture": 0.95}))
    report = build_report(png, body_part="chest", language="English")
    assert report["modality"] == "chest_xray"
    assert report["findings"][0]["label"] == "Fracture"
    assert report["summary"]["overall"] == "attention"
    assert "rib fracture" in report["explanation"].lower()


def test_healthy_chest_report_says_no_issues(png, monkeypatch):
    monkeypatch.setattr(radiology_report, "_analyze_chest",
                        _StubChestAnalyzer({"Fracture": 0.02, "Pneumonia": 0.05}))
    report = build_report(png, body_part="chest")
    assert report["summary"]["overall"] == "no_concerns"
    assert "no issues" in report["explanation"].lower()


def test_other_body_part_uses_vision_explainer_and_skips_chest_model(png, monkeypatch):
    chest = _StubChestAnalyzer({})
    monkeypatch.setattr(radiology_report, "_analyze_chest", chest)
    monkeypatch.setattr(
        radiology_report, "explain_other_xray",
        lambda path, language: {"modality": "xray_other", "summary": None, "model_name": "v",
                                "generated_by": "vision_llm", "explanation": "A hand."},
    )
    report = build_report(png, body_part="other")
    assert chest.seen == []
    assert report["findings"] == []
    assert report["explanation"] == "A hand."
    assert "processing_duration_seconds" in report


def test_pdf_upload_is_converted_and_temp_image_removed(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    Image.new("RGB", (30, 30), "gray").save(pdf, "PDF")
    chest = _StubChestAnalyzer({"Mass": 0.1})
    monkeypatch.setattr(radiology_report, "_analyze_chest", chest)
    build_report(pdf, body_part="chest", workdir=tmp_path)
    [seen] = chest.seen
    assert seen.suffix == ".png"
    assert not seen.exists()  # converted temp image is cleaned up
    assert pdf.exists()  # original upload untouched


def test_unknown_body_part_is_rejected(png):
    from backend.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        build_report(png, body_part="brain")


def _report(findings, generated_by="template"):
    return {
        "modality": "chest_xray", "model_name": "stub", "model_version": "pretrained",
        "findings": findings, "summary": {"overall": "attention"},
        "explanation": "text", "generated_by": generated_by,
        "processing_duration_seconds": 1.25, "disclaimer": "d",
    }


def test_save_report_persists_findings_inference_and_explanation():
    db, analysis = MagicMock(), MagicMock()
    save_report(db, analysis, _report([{"label": "Mass", "model_score": 0.9}]))

    added = [c.args[0] for c in db.add.call_args_list]
    assert sum(isinstance(a, RadiologyFinding) for a in added) == 1
    result_types = [getattr(a, "result_type", None) for a in added]
    assert ResultType.RADIOLOGY_INFERENCE in result_types
    explanation = next(a for a in added if getattr(a, "result_type", None) == ResultType.EXPLANATION)
    assert explanation.content["explanation"] == "text"
    assert explanation.content["summary"] == {"overall": "attention"}
    assert explanation.content["generated_by"] == "template"
    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.analysis_type == AnalysisType.XRAY
    assert analysis.processing_duration_seconds == "1.25"


def test_save_report_without_findings_stores_only_explanation():
    db, analysis = MagicMock(), MagicMock()
    save_report(db, analysis, _report([], generated_by="vision_llm"))
    result_types = [getattr(c.args[0], "result_type", None) for c in db.add.call_args_list]
    assert result_types == [ResultType.EXPLANATION]
