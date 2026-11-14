"""docs/CLARAMED_API.md is the contract JeevaCare's owner builds against; keep it in step with the code."""
from pathlib import Path

from backend.main import app
from backend.services.url_fetcher import FetchError  # noqa: F401  (error codes asserted below)

DOC = (Path(__file__).resolve().parents[2] / "docs" / "CLARAMED_API.md").read_text()


def test_every_integration_route_is_documented():
    paths = set(app.openapi()["paths"])
    assert {"/api/v1/analyze", "/api/v1/status/{job_id}"} <= paths
    assert "POST /api/v1/analyze" in DOC and "GET /api/v1/status/{jobId}" in DOC


def test_doc_covers_the_security_contract():
    for needle in ("X-ClaraMed-Signature", "X-ClaraMed-Timestamp", "sha256=", "Authorization: Bearer",
                   "allowed-host", "RESULT_RETENTION_DAYS", "CLARAMED_INTEGRATION_ENABLED",
                   "register_client.py", "raw body", "results: null", "STORAGE_PROVIDER=s3"):
        assert needle in DOC, needle


def test_doc_lists_every_public_error_code():
    for code in ("invalid_scheme", "invalid_url", "host_not_allowed", "blocked_address", "redirect_limit",
                 "too_large", "bad_content", "fetch_failed", "queue_unavailable", "integration_disabled",
                 "analysis_failed"):
        assert f"`{code}`" in DOC, code


def test_doc_states_the_accepted_field_names():
    for field in ("radiologyId", "documentId", "fileUrl", "imageUrl", "patientRef", "patientId", "hospitalRef"):
        assert field in DOC, field
