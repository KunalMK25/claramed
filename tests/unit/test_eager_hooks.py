"""Spike: prove Celery's eager mode fires AnalysisTask.on_success / on_failure (E2E tests rely on it)."""
import uuid

from backend.workers import tasks
from backend.workers.celery_app import celery_app
from backend.workers.tasks import AnalysisTask


def test_eager_apply_fires_the_finalize_hooks(monkeypatch):
    calls = []
    monkeypatch.setattr(tasks, "finalize_after_task", lambda analysis_id: calls.append(analysis_id))

    @celery_app.task(base=AnalysisTask, name="test.eager.ok")
    def ok(analysis_id):
        return "done"

    @celery_app.task(base=AnalysisTask, name="test.eager.bad")
    def bad(analysis_id):
        raise RuntimeError("boom")

    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    ok.apply(args=[first])
    bad.apply(args=[second])
    assert calls == [first, second]


def test_finalize_after_task_swallows_errors(monkeypatch):
    import backend.workers.callbacks as cb
    monkeypatch.setattr(cb, "finalize_integration_analysis", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    tasks.finalize_after_task(str(uuid.uuid4()))      # must not raise
