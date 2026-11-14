from datetime import datetime, timedelta

from backend.models.analysis import MedicalAnalysis
from backend.models.audit import AuditEvent
from backend.models.result import AnalysisResult, ResultType
from backend.workers.callbacks import purge_expired
from tests.support.factories import make_analysis


def _with_result(db, client, record, expires):
    a, _ = make_analysis(db, client, record=record, expire=expires)
    db.add(AnalysisResult(analysis_id=a.id, result_type=ResultType.RADIOLOGY_INFERENCE, content={}))
    db.commit()
    return a


def test_purges_only_expired(db, make_client):
    reg = make_client()
    now = datetime.utcnow()
    old = _with_result(db, reg.client, "old", now - timedelta(days=1))
    fresh = _with_result(db, reg.client, "fresh", now + timedelta(days=5))
    no_expiry = _with_result(db, reg.client, "none", None)
    assert purge_expired(db, now) == 1
    ids = {a.id for a in db.query(MedicalAnalysis).all()}
    assert old.id not in ids and fresh.id in ids and no_expiry.id in ids
    assert db.query(AnalysisResult).count() == 2          # cascade removed the old result


def test_audit_event_has_count_only(db, make_client):
    reg = make_client()
    _with_result(db, reg.client, "old", datetime.utcnow() - timedelta(days=1))
    purge_expired(db)
    event = db.query(AuditEvent).filter_by(action="results_purged").one()
    assert event.event_metadata == {"count": 1}


def test_nothing_to_purge_writes_no_event(db):
    assert purge_expired(db) == 0
    assert db.query(AuditEvent).filter_by(action="results_purged").count() == 0


def test_purge_also_removes_any_leftover_stored_file(db, make_client, storage_dir):
    reg = make_client()
    a, path = make_analysis(db, reg.client, expire=datetime.utcnow() - timedelta(days=1), file_in=storage_dir)
    purge_expired(db)
    assert not path.exists()
