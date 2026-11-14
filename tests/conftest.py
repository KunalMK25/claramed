"""
Pytest configuration. Runs against the PostgreSQL database `claramed_test`.

The models use PostgreSQL-only types (ARRAY, UUID), so SQLite cannot be used.
Create the database once with:  createdb -O claramed claramed_test
"""
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

# Must run before any backend import so settings and the global engine use the test DB.
_base_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
os.environ["DATABASE_URL"] = str(make_url(_base_url).set(database="claramed_test"))
_STORAGE = Path(tempfile.mkdtemp(prefix="claramed_storage_"))
os.environ["STORAGE_LOCAL_PATH"] = str(_STORAGE)
os.environ["STORAGE_PROVIDER"] = "local"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import backend.models  # noqa: E402,F401  (register every table on Base)
from backend.database.connection import Base, engine, get_db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.workers.celery_app import celery_app  # noqa: E402

_Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _eager_celery():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    yield


@pytest.fixture
def db():
    session = _Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def api_client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_storage():
    yield
    for child in _STORAGE.iterdir():
        shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)


@pytest.fixture
def storage_dir():
    return _STORAGE


@pytest.fixture
def sample_symptoms():
    """Sample symptom descriptions for testing."""
    return {
        "simple": "I have a headache",
        "detailed": "I have had a severe headache for 3 days, along with nausea and sensitivity to light.",
        "emergency": "Severe chest pain radiating to left arm, difficulty breathing",
    }


@pytest.fixture
def sample_languages():
    """Sample languages for testing."""
    return ["English", "Hindi", "Spanish"]


from backend.services.client_registry import register_client  # noqa: E402


@pytest.fixture
def make_client(db):
    """Register a client; returns RegisteredClient(client, api_key, webhook_secret)."""
    def _make(name="jeevacare", **overrides):
        params = dict(
            name=name,
            webhook_url="https://jeevacare.test/api/webhook/claramed-callback",
            allowed_file_hosts=["res.cloudinary.com"],
        )
        params.update(overrides)
        return register_client(db, **params)
    return _make


@pytest.fixture
def auth_headers():
    return lambda api_key: {"Authorization": f"Bearer {api_key}"}
