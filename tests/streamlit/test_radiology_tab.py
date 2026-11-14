from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


PAGE = str(Path(__file__).resolve().parents[2] / "app.py")
def new_app(secrets=None, state=None):
    at = AppTest.from_file(PAGE, default_timeout=30)
    at.secrets["GROQ_API_KEY"] = "test-key-not-real"   # the legacy tabs of the same app read this
    for key, value in (secrets or {}).items():
        at.secrets[key] = value
    for key, value in (state or {}).items():
        at.session_state[key] = value
    return at


def run(secrets=None, state=None):
    return new_app(secrets, state).run()


def test_radiology_ai_is_the_first_tab_of_the_one_page():
    at = run()
    assert [t.label for t in at.tabs][:2] == ["🩻 Radiology AI", "Symptom Checker"]


def test_page_shows_the_uploader_the_disclaimer_and_the_privacy_note():
    at = run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("not a diagnosis" in w.value.lower() for w in at.warning)
    assert any("separate" in i.value.lower() and "not saved" in i.value.lower() for i in at.info)
    assert at.file_uploader(key="radiology_upload"), "the X-ray uploader is missing"


def test_no_back_link_unless_configured():
    assert not run().get("link_button")


def test_back_link_appears_for_an_https_jeevacare_url():
    buttons = run(secrets={"JEEVACARE_URL": "https://jeevacare.example.com"}).get("link_button")
    assert len(buttons) == 1 and buttons[0].proto.url == "https://jeevacare.example.com"


def test_back_link_is_refused_for_non_https_urls():
    assert not run(secrets={"JEEVACARE_URL": "http://jeevacare.example.com"}).get("link_button")
    assert not run(secrets={"JEEVACARE_URL": "javascript:alert(1)"}).get("link_button")


# --- the real flow: upload, click Analyze, read the results (the model is faked so the test is fast) ---

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
MODEL_RESULT = {
    "findings": [{"label": "Edema", "model_score": 0.40}, {"label": "Pneumothorax", "model_score": 0.91},
                 {"label": "Lung_Lesion", "model_score": 0.12}, {"label": "Mass", "model_score": 0.05}],
    "disclaimer": "AI-generated output, not a radiologist's diagnosis.",
    "model_name": "densenet121-res224-all", "processing_duration_seconds": 1.2,
}


@pytest.fixture(autouse=True)
def scratch_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                      # the legacy tabs create their SQLite file in the working directory


@pytest.fixture
def fake_model(monkeypatch):
    created = []

    class FakeRadiologyService:
        def __init__(self):
            created.append(self)

        def load_model(self):
            return True

        def analyze_chest_xray(self, path):
            return MODEL_RESULT

    monkeypatch.setattr("backend.services.radiology_service.RadiologyService", FakeRadiologyService)
    st.cache_resource.clear()                     # the page caches the model per process; keep tests independent
    yield created
    st.cache_resource.clear()


def upload_and_analyze(filename, content):
    at = new_app().run()
    at.file_uploader(key="radiology_upload").upload(filename, content, "image/png")
    at.run()
    at.button(key="radiology_analyze").click().run()
    return at


def test_uploading_and_analyzing_shows_ranked_results(fake_model):
    at = upload_and_analyze("xray.png", PNG)
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error
    assert [m.label for m in at.metric] == ["Pneumothorax", "Edema", "Lung Lesion"]
    assert [m.value for m in at.metric] == ["91%", "40%", "12%"]
    assert len(at.dataframe) == 1
    assert any("radiologist" in c.value for c in at.caption)


def test_the_model_is_loaded_once_and_reused_across_analyses(fake_model):
    at = upload_and_analyze("xray.png", PNG)
    at.button(key="radiology_analyze").click().run()   # analyse again in the same session
    new_app().run()                                    # and a brand-new session
    assert len(fake_model) == 1


def test_a_file_that_is_not_an_image_gets_a_generic_error_and_never_reaches_the_model(fake_model):
    at = upload_and_analyze("report.png", b"%PDF-1.4 definitely not an image")
    assert not at.exception, [e.message for e in at.exception]
    assert [e.value for e in at.error] == ["This does not look like a PNG or JPEG image."]
    assert not at.metric and not at.dataframe
    assert fake_model == []                        # validation failed before the model was even loaded


def test_removing_the_upload_clears_the_results(fake_model):
    at = upload_and_analyze("xray.png", PNG)
    assert at.metric
    at.file_uploader(key="radiology_upload").clear()
    at.run()
    assert not at.metric and not at.dataframe
