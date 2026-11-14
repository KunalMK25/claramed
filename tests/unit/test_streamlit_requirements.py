"""The Streamlit app installs ONLY streamlit_app/requirements.txt. Keep it complete and lean."""
import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "streamlit_app"
ENTRY_POINTS = [APP / "app.py", APP / "pages" / "1_Radiology_AI.py"]
FIRST_PARTY = {"backend", "streamlit_app", "chains", "database"}
IMPORT_TO_DIST = {"PIL": "pillow", "skimage": "scikit-image", "PyPDF2": "pypdf2", "yaml": "pyyaml"}
BACKEND_ONLY = {"celery", "sqlalchemy", "psycopg2", "psycopg2-binary", "redis", "alembic", "boto3"}


def _first_party_file(module: str) -> Path | None:
    top = module.split(".")[0]
    base = APP if top in {"chains", "database"} else ROOT
    path = base / Path(*module.split("."))
    for candidate in (path.with_suffix(".py"), path / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def third_party_imports() -> set[str]:
    seen, found, queue = set(), set(), list(ENTRY_POINTS)
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            for module in modules:
                top = module.split(".")[0]
                if top in FIRST_PARTY:
                    target = _first_party_file(module)
                    if target:
                        queue.append(target)
                elif top not in sys.stdlib_module_names:
                    found.add(top)
    return found


def requirement_names() -> set[str]:
    names = set()
    for line in (APP / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            names.add(re.split(r"[<>=!~\[ ;]", line)[0].lower().replace("_", "-"))
    return names


def test_every_third_party_import_is_installed():
    needed = {IMPORT_TO_DIST.get(m, m).lower().replace("_", "-") for m in third_party_imports()}
    missing = sorted(needed - requirement_names())
    assert missing == [], f"add these to streamlit_app/requirements.txt: {missing}"


def test_the_closure_walk_really_reaches_the_heavy_imports():
    imports = third_party_imports()
    assert {"torch", "streamlit", "langchain_groq", "fastapi", "httpx"} <= imports   # guards the guard itself


def test_backend_only_packages_are_not_installed():
    assert sorted(requirement_names() & BACKEND_ONLY) == []


def test_pytorch_comes_from_the_cpu_index():
    first = (APP / "requirements.txt").read_text().splitlines()[0]
    assert first.strip() == "--extra-index-url https://download.pytorch.org/whl/cpu"


def test_uploads_are_capped_at_ten_megabytes_and_the_theme_is_kept():
    config = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())
    assert config["server"]["maxUploadSize"] == 10
    assert config["theme"]["base"] == "dark"


def test_secrets_template_has_placeholders_only():
    text = (APP / "secrets.toml.example").read_text()
    assert "GROQ_API_KEY" in text and "JEEVACARE_URL" in text
    assert not re.search(r"gsk_[A-Za-z0-9]{10,}", text)


def test_dev_frontend_image_runs_the_new_entry_point_and_the_lean_list():
    text = (ROOT / "Dockerfile.frontend").read_text()
    assert "streamlit_app/app.py" in text and "streamlit_app/requirements.txt" in text
