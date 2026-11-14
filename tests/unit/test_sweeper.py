from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from backend.models.analysis import AnalysisStatus
from backend.models.audit import AuditEvent
from backend.services.radiology_service import RadiologyService
from backend.workers import callbacks
from backend.workers.callbacks import sweep_stale_jobs
from backend.workers.tasks import process_radiology_async
from tests.support.factories import make_analysis

OLD = lambda: datetime.utcnow() - timedelta(hours=2)


@pytest.fixture
def enqueue(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(callbacks.deliver_callback, "delay", fake)
    return fake


@pytest.mark.parametrize("state", [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING])
def test_old_unfinished_job_is_failed_cleaned_up_and_called_back(db, make_client, storage_dir, enqueue, state):
    reg = make_client()
    a, path = make_analysis(db, reg.client, status=state, created_at=OLD(), delivery_status="pending",
                            file_in=storage_dir)
    assert sweep_stale_jobs(db) == 1
    db.refresh(a)
    assert a.status == AnalysisStatus.FAILED and a.processing_completed_at is not None
    assert a.results_expire_at is not None and not path.exists()
    enqueue.assert_called_once_with(str(a.id))
    assert db.query(AuditEvent).filter_by(action="stale_job_failed", resource_id=str(a.id)).count() == 1


def test_recent_completed_and_legacy_jobs_are_untouched(db, make_client, enqueue):
    reg = make_client()
    recent, _ = make_analysis(db, reg.client, record="r1", status=AnalysisStatus.PROCESSING,
                              created_at=datetime.utcnow() - timedelta(minutes=5))
    done, _ = make_analysis(db, reg.client, record="r2", status=AnalysisStatus.COMPLETED, created_at=OLD())
    legacy, _ = make_analysis(db, reg.client, status=AnalysisStatus.PROCESSING, created_at=OLD(), integration=False)
    assert sweep_stale_jobs(db) == 0
    for a in (recent, done, legacy):
        db.refresh(a)
    assert recent.status == AnalysisStatus.PROCESSING and done.status == AnalysisStatus.COMPLETED
    assert legacy.status == AnalysisStatus.PROCESSING
    enqueue.assert_not_called()


def test_a_swept_job_is_not_swept_twice(db, make_client, enqueue):
    reg = make_client()
    make_analysis(db, reg.client, status=AnalysisStatus.PROCESSING, created_at=OLD())
    assert sweep_stale_jobs(db) == 1
    assert sweep_stale_jobs(db) == 0
    assert enqueue.call_count == 1


def test_late_worker_cannot_overwrite_a_swept_job(db, make_client, storage_dir, monkeypatch):
    reg = make_client()
    a, _ = make_analysis(db, reg.client, status=AnalysisStatus.FAILED, file_in=storage_dir)
    doc = a.documents[0]
    monkeypatch.setattr(RadiologyService, "analyze_chest_xray",
                        lambda self, path: (_ for _ in ()).throw(AssertionError("must not run")))
    process_radiology_async.apply(args=[str(a.id), str(doc.id)])
    db.expire_all()
    assert db.get(type(a), a.id).status == AnalysisStatus.FAILED
