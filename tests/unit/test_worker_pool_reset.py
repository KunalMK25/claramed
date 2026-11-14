"""Forked Celery children must not reuse the parent's database connections."""
from unittest.mock import patch

from celery.signals import worker_process_init

import backend.workers.celery_app  # noqa: F401  (registers the signal handler)


def test_each_worker_child_discards_inherited_connections():
    with patch("backend.database.connection.engine") as engine:
        worker_process_init.send(sender=None)
    engine.dispose.assert_called_once_with(close=False)
