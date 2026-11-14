import json
import uuid

import httpx
import pytest

from backend.core.config import settings
from backend.models.analysis import AnalysisStatus
from backend.models.audit import AuditEvent
from backend.models.result import AnalysisResult, ResultType
from backend.workers import callbacks
from backend.workers.callbacks import backoff_seconds, build_callback_body, run_delivery_attempt
from tests.support.factories import make_analysis
from tests.support.jeevacare_stub import JeevaCareStub


@pytest.fixture
def setup(db, make_client):
    reg = make_client()
    a, _ = make_analysis(db, reg.client)
    db.add(AnalysisResult(analysis_id=a.id, result_type=ResultType.RADIOLOGY_INFERENCE, content={
        "findings": [{"label": "Edema", "model_score": 0.9}], "disclaimer": "d"}))
    db.commit()
    return a, JeevaCareStub(reg.webhook_secret), reg


def test_body_is_canonical_and_complete(db, setup):
    a, _, _ = setup
    raw = build_callback_body(db, a)
    body = json.loads(raw)
    assert body["jobId"] == str(a.id) and body["status"] == "completed"
    assert body["radiologyId"] == "rad-1" and body["error"] is None
    assert body["results"]["findings"][0]["label"] == "Edema"
    assert raw == json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def test_document_body_uses_document_id(db, make_client):
    reg = make_client()
    a, _ = make_analysis(db, reg.client, record="doc-1", kind="document")
    body = json.loads(build_callback_body(db, a))
    assert body["documentId"] == "doc-1" and "radiologyId" not in body


def test_failed_analysis_sends_generic_error(db, setup):
    a, _, _ = setup
    a.status = AnalysisStatus.FAILED
    a.error_message = "Traceback: secret internals"
    db.commit()
    body = json.loads(build_callback_body(db, a))
    assert body["status"] == "failed" and body["results"] is None
    assert body["error"] == {"code": "analysis_failed"}
    assert "Traceback" not in json.dumps(body)


def test_delivers_with_valid_signature(db, setup):
    a, stub, _ = setup
    assert run_delivery_attempt(db, str(a.id), 0, stub.client()) == "delivered"
    db.refresh(a)
    assert a.delivery_status == "delivered" and a.delivery_attempts == 1
    assert a.callback_delivered_at is not None
    assert stub.received[0]["jobId"] == str(a.id)


def test_bearer_token_is_sent_when_configured(db, make_client):
    reg = make_client(callback_auth_token="jv-token")
    a, _ = make_analysis(db, reg.client)
    stub = JeevaCareStub(reg.webhook_secret, expected_token="jv-token")
    assert run_delivery_attempt(db, str(a.id), 0, stub.client()) == "delivered"
    assert stub.headers_seen[0]["authorization"] == "Bearer jv-token"


def test_no_authorization_header_without_a_token(db, setup):
    a, stub, _ = setup
    run_delivery_attempt(db, str(a.id), 0, stub.client())
    assert "authorization" not in stub.headers_seen[0]


def test_wrong_token_is_rejected_and_retried(db, make_client):
    reg = make_client(callback_auth_token="jv-token")
    a, _ = make_analysis(db, reg.client)
    stub = JeevaCareStub(reg.webhook_secret, expected_token="other")
    assert run_delivery_attempt(db, str(a.id), 0, stub.client()) == "retry"
    assert stub.received == []


def test_server_error_requests_retry(db, setup):
    a, stub, _ = setup
    stub.fail_next = 1
    assert run_delivery_attempt(db, str(a.id), 0, stub.client()) == "retry"
    db.refresh(a)
    assert a.delivery_status == "pending" and a.delivery_attempts == 1
    assert "500" in a.delivery_last_error


def test_wrong_secret_is_rejected_and_retried(db, setup):
    a, _, _ = setup
    bad = JeevaCareStub("not-the-secret")
    assert run_delivery_attempt(db, str(a.id), 0, bad.client()) == "retry"
    assert bad.received == []


def test_connection_error_requests_retry(db, setup):
    a, _, _ = setup

    def boom(request):
        raise httpx.ConnectError("down")
    assert run_delivery_attempt(db, str(a.id), 0, httpx.Client(transport=httpx.MockTransport(boom))) == "retry"


def test_redirect_is_not_followed(db, setup):
    a, _, _ = setup
    hits = []

    def redirect(request):
        hits.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example/x"})
    client = httpx.Client(transport=httpx.MockTransport(redirect), follow_redirects=False)
    assert run_delivery_attempt(db, str(a.id), 0, client) == "retry"
    assert hits == ["https://jeevacare.test/api/webhook/claramed-callback"]


def test_exhaustion_marks_failed_after_max_attempts(db, setup):
    a, stub, _ = setup
    stub.fail_next = 99
    n = settings.CALLBACK_MAX_ATTEMPTS
    outcomes = [run_delivery_attempt(db, str(a.id), i, stub.client()) for i in range(n)]
    assert outcomes[:-1] == ["retry"] * (n - 1) and outcomes[-1] == "failed"
    db.refresh(a)
    assert a.delivery_status == "failed" and a.delivery_attempts == n


def test_retry_then_success(db, setup):
    a, stub, _ = setup
    stub.fail_next = 2
    outcomes = [run_delivery_attempt(db, str(a.id), i, stub.client()) for i in range(3)]
    assert outcomes == ["retry", "retry", "delivered"]


def test_already_delivered_is_not_resent(db, setup):
    a, stub, _ = setup
    run_delivery_attempt(db, str(a.id), 0, stub.client())
    assert run_delivery_attempt(db, str(a.id), 1, stub.client()) == "delivered"
    assert len(stub.received) == 1


def test_deactivated_client_makes_no_http_call(db, setup):
    a, stub, reg = setup
    reg.client.active = False
    db.commit()
    assert run_delivery_attempt(db, str(a.id), 0, stub.client()) == "failed"
    db.refresh(a)
    assert a.delivery_status == "skipped" and stub.requests == 0


def test_unknown_analysis_returns_failed(db):
    assert run_delivery_attempt(db, str(uuid.uuid4()), 0, httpx.Client()) == "failed"


def test_each_attempt_is_audited_without_patient_refs(db, setup):
    a, stub, _ = setup
    a.external_patient_reference = "JV-PAT-SECRET"
    db.commit()
    stub.fail_next = 1
    run_delivery_attempt(db, str(a.id), 0, stub.client())
    run_delivery_attempt(db, str(a.id), 1, stub.client())
    events = db.query(AuditEvent).filter_by(action="callback_attempt").all()
    assert sorted(e.outcome for e in events) == ["failure", "success"]
    assert "JV-PAT-SECRET" not in json.dumps([e.event_metadata for e in events])


def test_backoff_totals_about_thirty_minutes():
    assert [backoff_seconds(n) for n in range(4)] == [120, 240, 480, 960]
    assert sum(backoff_seconds(n) for n in range(4)) == 1800


def test_celery_wrapper_retries_with_increasing_attempt_index(db, setup, monkeypatch):
    a, stub, _ = setup
    seen = []

    def fake_attempt(db_, analysis_id, attempt_index, http):
        seen.append(attempt_index)
        return "retry" if attempt_index == 0 else "delivered"

    monkeypatch.setattr(callbacks, "run_delivery_attempt", fake_attempt)
    monkeypatch.setattr(callbacks, "_http_client", stub.client)
    monkeypatch.setattr(callbacks, "backoff_seconds", lambda n: 0)
    callbacks.deliver_callback.apply(args=[str(a.id)])
    assert seen == [0, 1]
