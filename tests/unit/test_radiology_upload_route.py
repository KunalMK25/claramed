"""Endpoint wiring tests for POST /analyses/{id}/images (model + storage stubbed)."""
import io
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.api.dependencies import require_authentication
from backend.api.routes import analyses as routes
from backend.database.connection import get_db


@pytest.fixture
def env(monkeypatch):
    analysis = MagicMock(id=uuid.uuid4(), language="Hindi")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = analysis

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_authentication] = lambda: MagicMock()

    calls = {}

    def fake_build_report(path, body_part="chest", language="English", workdir=None):
        calls.update(body_part=body_part, language=language, suffix=path.suffix)
        return {
            "modality": "chest_xray", "model_name": "stub", "model_version": "p",
            "findings": [{"label": "Fracture", "model_score": 0.9}],
            "summary": {"overall": "attention"}, "explanation": "## Plain English",
            "generated_by": "template", "processing_duration_seconds": 0.1, "disclaimer": "d",
        }

    storage = MagicMock()
    storage.generate_storage_key.return_value = "images/a/x.png"
    storage.save_file.return_value = {"storage_provider": "local"}
    monkeypatch.setattr(routes, "check_analysis_access", lambda *a, **k: True)
    monkeypatch.setattr(routes, "build_report", fake_build_report)
    monkeypatch.setattr(routes, "save_report", MagicMock())
    monkeypatch.setattr(routes, "StorageService", lambda: storage)
    return TestClient(app), analysis, db, calls


def _png_bytes():
    buf = io.BytesIO()
    Image.new("L", (8, 8)).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("name", ["scan.png", "scan.JPG", "scan.pdf", "scan.dcm"])
def test_supported_formats_return_plain_english_explanation(env, name):
    client, analysis, _, calls = env
    r = client.post(f"/analyses/{analysis.id}/images",
                    files={"file": (name, _png_bytes(), "application/octet-stream")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["explanation"] == "## Plain English"
    assert body["overall"] == "attention"
    assert calls["language"] == "Hindi"  # uses the analysis language
    assert calls["body_part"] == "chest"  # default


def test_body_part_other_is_passed_through(env):
    client, analysis, _, calls = env
    r = client.post(f"/analyses/{analysis.id}/images", data={"body_part": "other"},
                    files={"file": ("hand.png", _png_bytes(), "image/png")})
    assert r.status_code == 201
    assert calls["body_part"] == "other"


def test_unsupported_extension_is_rejected(env):
    client, analysis, _, _ = env
    r = client.post(f"/analyses/{analysis.id}/images",
                    files={"file": ("scan.gif", b"x", "image/gif")})
    assert r.status_code == 400


def test_invalid_body_part_is_rejected(env):
    client, analysis, _, _ = env
    r = client.post(f"/analyses/{analysis.id}/images", data={"body_part": "brain"},
                    files={"file": ("a.png", _png_bytes(), "image/png")})
    assert r.status_code == 400


def test_upload_commits_once_on_success(env):
    client, analysis, db, _ = env
    client.post(f"/analyses/{analysis.id}/images",
                files={"file": ("a.png", _png_bytes(), "image/png")})
    db.commit.assert_called_once()


def test_unauthenticated_upload_is_rejected(env):
    client, analysis, _, calls = env
    client.app.dependency_overrides.pop(require_authentication)
    r = client.post(f"/analyses/{analysis.id}/images",
                    files={"file": ("a.png", _png_bytes(), "image/png")})
    assert r.status_code == 401
    assert calls == {}  # nothing was analyzed
