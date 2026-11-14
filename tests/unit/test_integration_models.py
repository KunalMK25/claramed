import pytest
from sqlalchemy.exc import IntegrityError

from backend.core.config import settings
from backend.models.analysis import AnalysisType, MedicalAnalysis
from backend.models.integration_client import IntegrationClient


def _client(db, name="jeevacare"):
    c = IntegrationClient(
        client_name=name,
        hashed_api_key=f"hash-{name}",
        scopes=["analysis:create"],
        webhook_url="https://jeevacare.test/api/webhook/claramed-callback",
        webhook_secret="s3cret",
        callback_auth_token="tok",
        allowed_file_hosts=["res.cloudinary.com"],
    )
    db.add(c)
    db.commit()
    return c


def test_client_stores_webhook_config(db):
    c = _client(db)
    db.refresh(c)
    assert c.webhook_url.startswith("https://")
    assert c.callback_auth_token == "tok"
    assert c.allowed_file_hosts == ["res.cloudinary.com"]


def test_same_record_twice_for_one_client_is_rejected(db):
    c = _client(db)
    for _ in range(2):
        db.add(MedicalAnalysis(
            analysis_type=AnalysisType.XRAY,
            requesting_client_id=c.id,
            external_record_kind="radiology",
            external_record_id="rad-1",
        ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_record_id_for_different_clients_is_allowed(db):
    a, b = _client(db, "a"), _client(db, "b")
    for c in (a, b):
        db.add(MedicalAnalysis(
            analysis_type=AnalysisType.XRAY,
            requesting_client_id=c.id,
            external_record_kind="radiology",
            external_record_id="rad-1",
        ))
    db.commit()


def test_legacy_analyses_without_record_id_do_not_collide(db):
    c = _client(db)
    for _ in range(2):
        db.add(MedicalAnalysis(analysis_type=AnalysisType.XRAY, requesting_client_id=c.id))
    db.commit()


def test_delivery_attempts_defaults_to_zero(db):
    c = _client(db)
    a = MedicalAnalysis(analysis_type=AnalysisType.XRAY, requesting_client_id=c.id)
    db.add(a)
    db.commit()
    assert a.delivery_attempts == 0


def test_integration_settings_have_documented_defaults():
    assert settings.CLARAMED_INTEGRATION_ENABLED is True
    assert settings.CALLBACK_MAX_ATTEMPTS == 5
    assert settings.CALLBACK_BACKOFF_BASE_SECONDS == 120
    assert settings.CALLBACK_TIMEOUT_SECONDS == 10
    assert settings.RESULT_RETENTION_DAYS == 30
    assert settings.STALE_JOB_SECONDS == 1800
