from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[2] / "streamlit_app"


def test_home_page_starts_without_an_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                       # the app creates its SQLite file in the working directory
    monkeypatch.syspath_prepend(str(APP_DIR))         # `import chains` / `import database` are script-relative
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.secrets["GROQ_API_KEY"] = "test-key-not-real"
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert "ClaraMed" in " ".join(m.value for m in at.markdown)
