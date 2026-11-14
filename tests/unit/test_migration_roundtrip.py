"""Alembic upgrade -> downgrade -> upgrade on a throwaway database."""
import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backend.core.config import settings

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _alembic(url, *args):
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )


@pytest.fixture
def scratch_db():
    base = make_url(settings.DATABASE_URL)
    name = f"claramed_mig_{uuid.uuid4().hex[:8]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name)
    try:
        yield url.render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _columns(url, table):
    engine = create_engine(url)
    try:
        return {c["name"] for c in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade_roundtrip(scratch_db):
    up = _alembic(scratch_db, "upgrade", "head")
    assert up.returncode == 0, up.stderr[-800:]
    assert {"external_record_id", "delivery_status", "results_expire_at"} <= _columns(scratch_db, "medical_analyses")
    assert {"webhook_url", "webhook_secret", "callback_auth_token", "allowed_file_hosts"} <= _columns(
        scratch_db, "integration_clients")

    down = _alembic(scratch_db, "downgrade", "-1")
    assert down.returncode == 0, down.stderr[-800:]
    assert "external_record_id" not in _columns(scratch_db, "medical_analyses")
    assert "webhook_url" not in _columns(scratch_db, "integration_clients")

    again = _alembic(scratch_db, "upgrade", "head")
    assert again.returncode == 0, again.stderr[-800:]
    assert "external_record_id" in _columns(scratch_db, "medical_analyses")
