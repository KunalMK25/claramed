import uuid
from datetime import datetime, timedelta

import pytest

ID = str(uuid.uuid4())
ROUTES = [
    ("post", "/api/v1/analyses", {"json": {"input_text": "headache", "language": "English"}}),
    ("get", "/api/v1/analyses", {}),
    ("get", f"/api/v1/analyses/{ID}", {}),
    ("get", f"/api/v1/analyses/{ID}/results", {}),
    ("post", f"/api/v1/analyses/{ID}/documents", {"files": {"file": ("a.pdf", b"%PDF-1.4", "application/pdf")}}),
    ("post", f"/api/v1/analyses/{ID}/images", {"files": {"file": ("a.png", b"\x89PNG", "image/png")}}),
]


@pytest.mark.parametrize("method,path,kwargs", ROUTES)
def test_anonymous_request_is_rejected(api_client, method, path, kwargs):
    assert getattr(api_client, method)(path, **kwargs).status_code == 401


def test_valid_key_is_accepted(api_client, make_client, auth_headers):
    reg = make_client()
    assert api_client.get("/api/v1/analyses", headers=auth_headers(reg.api_key)).status_code == 200


def test_wrong_key_is_rejected(api_client, make_client, auth_headers):
    make_client()
    assert api_client.get("/api/v1/analyses", headers=auth_headers("sk_claramed_wrong")).status_code == 401


def test_non_bearer_scheme_is_rejected(api_client, make_client):
    reg = make_client()
    r = api_client.get("/api/v1/analyses", headers={"Authorization": f"Basic {reg.api_key}"})
    assert r.status_code == 401


def test_inactive_client_key_is_rejected(api_client, make_client, auth_headers, db):
    reg = make_client()
    reg.client.active = False
    db.commit()
    assert api_client.get("/api/v1/analyses", headers=auth_headers(reg.api_key)).status_code == 401


def test_last_used_is_set_then_throttled(api_client, make_client, auth_headers, db):
    reg = make_client()
    headers = auth_headers(reg.api_key)
    assert reg.client.last_used_at is None
    api_client.get("/api/v1/analyses", headers=headers)
    db.refresh(reg.client)
    first = reg.client.last_used_at
    assert first is not None
    api_client.get("/api/v1/analyses", headers=headers)
    db.refresh(reg.client)
    assert reg.client.last_used_at == first          # within 60 s: no new write

    reg.client.last_used_at = datetime.utcnow() - timedelta(minutes=5)
    db.commit()
    stale = reg.client.last_used_at
    api_client.get("/api/v1/analyses", headers=headers)
    db.refresh(reg.client)
    assert reg.client.last_used_at > stale           # older than 60 s: refreshed
