from datetime import datetime, timedelta
from unittest.mock import MagicMock

from backend.core.config import settings
from backend.models.audit import AuditEvent
from backend.workers.callbacks import finalize_integration_analysis
from tests.support.factories import make_analysis


def test_deletes_file_sets_expiry_and_enqueues(db, make_client, storage_dir):
    reg = make_client()
    a, path = make_analysis(db, reg.client, file_in=storage_dir)
    enqueue = MagicMock()
    assert finalize_integration_analysis(db, str(a.id), enqueue=enqueue) is True
    assert not path.exists()
    db.refresh(a)
    expected = datetime.utcnow() + timedelta(days=settings.RESULT_RETENTION_DAYS)
    assert abs((a.results_expire_at - expected).total_seconds()) < 60
    enqueue.assert_called_once_with(str(a.id))
    assert db.query(AuditEvent).filter_by(action="file_deleted", resource_id=str(a.id)).count() == 1


def test_second_call_is_a_noop(db, make_client, storage_dir):
    reg = make_client()
    a, _ = make_analysis(db, reg.client, file_in=storage_dir)
    enqueue = MagicMock()
    finalize_integration_analysis(db, str(a.id), enqueue=enqueue)
    assert finalize_integration_analysis(db, str(a.id), enqueue=enqueue) is False
    assert enqueue.call_count == 1


def test_legacy_analysis_is_untouched(db, make_client, storage_dir):
    reg = make_client()
    a, path = make_analysis(db, reg.client, integration=False, file_in=storage_dir)
    enqueue = MagicMock()
    assert finalize_integration_analysis(db, str(a.id), enqueue=enqueue) is False
    assert path.exists() and not enqueue.called


def test_missing_file_does_not_block_the_callback(db, make_client, storage_dir):
    reg = make_client()
    a, path = make_analysis(db, reg.client, file_in=storage_dir)
    path.unlink()
    enqueue = MagicMock()
    assert finalize_integration_analysis(db, str(a.id), enqueue=enqueue) is True
    enqueue.assert_called_once()


def test_unknown_analysis_is_a_noop(db):
    import uuid
    assert finalize_integration_analysis(db, str(uuid.uuid4()), enqueue=MagicMock()) is False


def test_client_without_webhook_is_skipped_but_still_cleaned_up(db, make_client, storage_dir):
    reg = make_client()
    reg.client.webhook_url = None
    db.commit()
    a, path = make_analysis(db, reg.client, file_in=storage_dir)
    enqueue = MagicMock()
    assert finalize_integration_analysis(db, str(a.id), enqueue=enqueue) is True
    db.refresh(a)
    assert a.delivery_status == "skipped" and not enqueue.called and not path.exists()
    assert a.results_expire_at is not None


def test_deactivated_client_is_skipped(db, make_client, storage_dir):
    reg = make_client()
    reg.client.active = False
    db.commit()
    a, _ = make_analysis(db, reg.client, file_in=storage_dir)
    enqueue = MagicMock()
    finalize_integration_analysis(db, str(a.id), enqueue=enqueue)
    db.refresh(a)
    assert a.delivery_status == "skipped" and not enqueue.called
