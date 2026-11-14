import uuid
from unittest.mock import MagicMock

import pytest

from backend.core.config import settings
from backend.models.analysis import AnalysisStatus, MedicalAnalysis
from backend.models.audit import AuditEvent
from backend.models.document import UploadedDocument
from backend.models.result import AnalysisResult, ResultType
from backend.services import integration_service
from backend.services.url_fetcher import FetchedFile, FetchError

PNG = FetchedFile(content=b"\x89PNG\r\n\x1a\n" + b"0" * 32, kind_detected="png", extension=".png")
PDF = FetchedFile(content=b"%PDF-1.4\n" + b"0" * 32, kind_detected="pdf", extension=".pdf")
BODY = {"type": "radiology", "radiologyId": "rad-1",
        "fileUrl": "https://res.cloudinary.com/x/xray.png",
        "patientRef": "JV-PAT-1", "hospitalRef": "JV-HOSP-1"}
# The exact shape JeevaCare's own integration guide sends (no `type`, imageUrl, patientId).
JEEVACARE_DOC_BODY = {"radiologyId": "rad-77", "imageUrl": "https://res.cloudinary.com/x/signed.png",
                      "patientId": "JV-PAT-9", "metadata": {"modality": "chest_xray"}}


@pytest.fixture
def tasks(monkeypatch):
    rad, doc = MagicMock(), MagicMock()
    monkeypatch.setattr(integration_service, "process_radiology_async", rad)
    monkeypatch.setattr(integration_service, "process_document_async", doc)
    return rad, doc


@pytest.fixture
def fetched(monkeypatch):
    fake = MagicMock(return_value=PNG)
    monkeypatch.setattr(integration_service, "fetch_file", fake)
    return fake


@pytest.fixture
def auth(make_client, auth_headers):
    reg = make_client()
    return reg, auth_headers(reg.api_key)


def _stored(storage_dir):
    return [p for p in storage_dir.rglob("*") if p.is_file()]


def test_anonymous_is_401(api_client):
    assert api_client.post("/api/v1/analyze", json=BODY).status_code == 401
    assert api_client.get(f"/api/v1/status/{uuid.uuid4()}").status_code == 401


def test_missing_scope_is_403(api_client, make_client, auth_headers):
    reg = make_client(scopes=["analysis:read"])
    assert api_client.post("/api/v1/analyze", json=BODY, headers=auth_headers(reg.api_key)).status_code == 403
    reg2 = make_client("b", scopes=["analysis:create"])
    assert api_client.get(f"/api/v1/status/{uuid.uuid4()}", headers=auth_headers(reg2.api_key)).status_code == 403


@pytest.mark.parametrize("patch", [
    {"radiologyId": None},                                     # no id at all
    {"documentId": "d1"},                                      # both ids
    {"type": "document"},                                      # type does not match the id sent
    {"fileUrl": "not-a-url"},
    {"imageUrl": "https://res.cloudinary.com/x/y.png"},        # both URL fields
    {"fileUrl": None},                                         # no URL at all
])
def test_invalid_body_is_422(api_client, auth, tasks, fetched, patch):
    _, headers = auth
    body = {k: v for k, v in {**BODY, **patch}.items() if v is not None}
    assert api_client.post("/api/v1/analyze", json=body, headers=headers).status_code == 422


def test_radiology_submit_creates_job_and_enqueues(api_client, auth, tasks, fetched, db, storage_dir):
    reg, headers = auth
    r = api_client.post("/api/v1/analyze", json=BODY, headers=headers)
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    analysis = db.get(MedicalAnalysis, uuid.UUID(data["jobId"]))
    assert analysis.requesting_client_id == reg.client.id
    assert analysis.external_record_kind == "radiology" and analysis.external_record_id == "rad-1"
    assert analysis.external_patient_reference == "JV-PAT-1"
    assert analysis.external_system == "jeevacare"
    assert analysis.delivery_status == "pending"
    docs = db.query(UploadedDocument).filter_by(analysis_id=analysis.id).all()
    assert len(docs) == 1 and (storage_dir / docs[0].storage_key).exists()
    tasks[0].delay.assert_called_once_with(str(analysis.id), str(docs[0].id))
    assert fetched.call_args.kwargs["allowed_hosts"] == ["res.cloudinary.com"]
    assert fetched.call_args.kwargs["kind"] == "radiology"
    assert db.query(AuditEvent).filter_by(action="analysis_submitted").count() == 1


def test_accepts_jeevacare_documented_field_names(api_client, auth, tasks, fetched, db):
    _, headers = auth
    r = api_client.post("/api/v1/analyze", json=JEEVACARE_DOC_BODY, headers=headers)
    assert r.status_code == 202
    analysis = db.get(MedicalAnalysis, uuid.UUID(r.json()["jobId"]))
    assert analysis.external_record_kind == "radiology"          # type inferred
    assert analysis.external_patient_reference == "JV-PAT-9"     # patientId alias
    assert fetched.call_args.args[0] == "https://res.cloudinary.com/x/signed.png"   # imageUrl alias


def test_document_submit_enqueues_document_task(api_client, auth, tasks, monkeypatch):
    monkeypatch.setattr(integration_service, "fetch_file", MagicMock(return_value=PDF))
    _, headers = auth
    body = {"documentId": "doc-9", "fileUrl": "https://res.cloudinary.com/x/r.pdf"}
    r = api_client.post("/api/v1/analyze", json=body, headers=headers)
    assert r.status_code == 202
    tasks[1].delay.assert_called_once()
    tasks[0].delay.assert_not_called()


def test_resubmit_is_idempotent(api_client, auth, tasks, fetched, db):
    _, headers = auth
    first = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()
    second = api_client.post("/api/v1/analyze", json=BODY, headers=headers)
    assert second.status_code == 202 and second.json()["jobId"] == first["jobId"]
    assert db.query(MedicalAnalysis).count() == 1
    assert fetched.call_count == 1 and tasks[0].delay.call_count == 1


def test_completed_job_is_also_idempotent(api_client, auth, tasks, fetched, db):
    _, headers = auth
    first = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()
    db.get(MedicalAnalysis, uuid.UUID(first["jobId"])).status = AnalysisStatus.COMPLETED
    db.commit()
    again = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()
    assert again["jobId"] == first["jobId"] and again["status"] == "completed"


def test_failed_job_is_replaced_on_resubmit(api_client, auth, tasks, fetched, db):
    _, headers = auth
    first = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()["jobId"]
    old = db.get(MedicalAnalysis, uuid.UUID(first))
    old.status = AnalysisStatus.FAILED
    db.commit()
    second = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()["jobId"]
    assert second != first
    assert db.query(MedicalAnalysis).count() == 1
    assert db.get(MedicalAnalysis, uuid.UUID(second)).status == AnalysisStatus.PENDING
    assert tasks[0].delay.call_count == 2
    assert db.query(AuditEvent).filter_by(action="failed_job_replaced").count() == 1


def test_failed_job_survives_a_bad_resubmit(api_client, auth, tasks, fetched, monkeypatch, db):
    _, headers = auth
    first = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()["jobId"]
    db.get(MedicalAnalysis, uuid.UUID(first)).status = AnalysisStatus.FAILED
    db.commit()
    monkeypatch.setattr(integration_service, "fetch_file", MagicMock(side_effect=FetchError("bad_content", "x")))
    assert api_client.post("/api/v1/analyze", json=BODY, headers=headers).status_code == 422
    assert db.get(MedicalAnalysis, uuid.UUID(first)) is not None     # the failed record is still there


def test_concurrent_duplicate_submit_returns_the_existing_job(api_client, auth, tasks, fetched, monkeypatch, db):
    reg, headers = auth
    existing = MedicalAnalysis(analysis_type=integration_service.AnalysisType.XRAY,
                               requesting_client_id=reg.client.id, status=AnalysisStatus.PENDING,
                               external_record_kind="radiology", external_record_id="rad-1")
    db.add(existing)
    db.commit()
    real = integration_service._find_existing
    calls = {"n": 0}

    def racing(*a, **k):                       # first look misses (the other request has not committed yet)
        calls["n"] += 1
        return None if calls["n"] == 1 else real(*a, **k)

    monkeypatch.setattr(integration_service, "_find_existing", racing)
    r = api_client.post("/api/v1/analyze", json=BODY, headers=headers)
    assert r.status_code == 202 and r.json()["jobId"] == str(existing.id)
    assert db.query(MedicalAnalysis).count() == 1
    tasks[0].delay.assert_not_called()


def test_intake_failure_creates_nothing(api_client, auth, tasks, monkeypatch, db, storage_dir):
    monkeypatch.setattr(integration_service, "fetch_file",
                        MagicMock(side_effect=FetchError("host_not_allowed", "nope")))
    _, headers = auth
    r = api_client.post("/api/v1/analyze", json=BODY, headers=headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "host_not_allowed"
    assert db.query(MedicalAnalysis).count() == 0 and _stored(storage_dir) == []
    tasks[0].delay.assert_not_called()


def test_queue_outage_rolls_everything_back_and_returns_503(api_client, auth, tasks, fetched, db, storage_dir):
    _, headers = auth
    tasks[0].delay.side_effect = ConnectionError("redis down")
    r = api_client.post("/api/v1/analyze", json=BODY, headers=headers)
    assert r.status_code == 503 and r.json()["error"]["code"] == "queue_unavailable"
    assert db.query(MedicalAnalysis).count() == 0
    assert _stored(storage_dir) == []
    assert db.query(AuditEvent).filter_by(action="analysis_enqueue_failed").count() == 1
    tasks[0].delay.side_effect = None                      # queue recovers; a retry now works
    assert api_client.post("/api/v1/analyze", json=BODY, headers=headers).status_code == 202


def test_kill_switch_returns_503(api_client, auth, tasks, fetched, monkeypatch):
    monkeypatch.setattr(settings, "CLARAMED_INTEGRATION_ENABLED", False)
    _, headers = auth
    assert api_client.post("/api/v1/analyze", json=BODY, headers=headers).status_code == 503


def test_status_is_scoped_to_owner(api_client, make_client, auth_headers, tasks, fetched):
    a, b = make_client("a"), make_client("b")
    job = api_client.post("/api/v1/analyze", json=BODY, headers=auth_headers(a.api_key)).json()["jobId"]
    assert api_client.get(f"/api/v1/status/{job}", headers=auth_headers(b.api_key)).status_code == 404
    assert api_client.get("/api/v1/status/not-a-uuid", headers=auth_headers(a.api_key)).status_code == 404
    mine = api_client.get(f"/api/v1/status/{job}", headers=auth_headers(a.api_key))
    assert mine.status_code == 200 and mine.json()["status"] == "queued"
    assert mine.json()["radiologyId"] == "rad-1" and mine.json()["results"] is None


def test_same_record_id_for_two_clients_is_independent(api_client, make_client, auth_headers, tasks, fetched):
    a, b = make_client("a"), make_client("b")
    ja = api_client.post("/api/v1/analyze", json=BODY, headers=auth_headers(a.api_key)).json()["jobId"]
    jb = api_client.post("/api/v1/analyze", json=BODY, headers=auth_headers(b.api_key)).json()["jobId"]
    assert ja != jb


def test_status_returns_radiology_results_when_completed(api_client, auth, tasks, fetched, db):
    _, headers = auth
    job = api_client.post("/api/v1/analyze", json=BODY, headers=headers).json()["jobId"]
    analysis = db.get(MedicalAnalysis, uuid.UUID(job))
    analysis.status = AnalysisStatus.COMPLETED
    db.add(AnalysisResult(analysis_id=analysis.id, result_type=ResultType.RADIOLOGY_INFERENCE, content={
        "modality": "chest_xray", "model_name": "densenet121-res224-all", "disclaimer": "Not a diagnosis.",
        "findings": [{"label": "Edema", "model_score": 0.81}, {"label": "Atelectasis", "model_score": 0.2}],
    }))
    db.commit()
    body = api_client.get(f"/api/v1/status/{job}", headers=headers).json()
    assert body["status"] == "completed"
    assert body["results"]["findings"][0] == {"label": "Edema", "score": 0.81}
    assert body["results"]["confidence"] == 0.81
    assert "Edema" in body["results"]["summary"]
    assert body["results"]["disclaimer"] == "Not a diagnosis."


def test_status_returns_document_results_when_completed(api_client, auth, tasks, monkeypatch, db):
    monkeypatch.setattr(integration_service, "fetch_file", MagicMock(return_value=PDF))
    _, headers = auth
    job = api_client.post("/api/v1/analyze", headers=headers,
                          json={"documentId": "d-1", "fileUrl": "https://res.cloudinary.com/x/r.pdf"}).json()["jobId"]
    analysis = db.get(MedicalAnalysis, uuid.UUID(job))
    analysis.status = AnalysisStatus.COMPLETED
    db.add(AnalysisResult(analysis_id=analysis.id, result_type=ResultType.EXPLANATION,
                          content={"explanation": "Your hemoglobin is low."}))
    db.add(AnalysisResult(analysis_id=analysis.id, result_type=ResultType.STRUCTURED_FINDINGS,
                          content={"findings": [{"test": "Hemoglobin", "value": 9.1}]}))
    db.commit()
    body = api_client.get(f"/api/v1/status/{job}", headers=headers).json()
    assert body["documentId"] == "d-1"
    assert body["results"]["explanation"] == "Your hemoglobin is low."
    assert body["results"]["findings"] == [{"test": "Hemoglobin", "value": 9.1}]
