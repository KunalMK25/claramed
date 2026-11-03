"""
Pytest Configuration and Fixtures
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.connection import Base
from backend.core.config import settings

# Test database URL
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


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
