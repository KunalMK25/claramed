from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]


def test_home_page_starts_without_an_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                       # the app creates its SQLite file in the working directory
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.secrets["GROQ_API_KEY"] = "test-key-not-real"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert "ClaraMed" in " ".join(m.value for m in at.markdown)


def test_the_streamlit_entry_point_is_the_root_app_py():
    # Streamlit Community Cloud is configured with `app.py`; it must never move again.
    assert (ROOT / "app.py").exists() and not (ROOT / "streamlit_app" / "app.py").exists()
