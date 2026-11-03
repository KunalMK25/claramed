"""
Database Initialization Script

This script initializes the ClaraMed database by creating all tables.
Use Alembic migrations for production environments.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.connection import engine, Base
from backend.models import (
    MedicalAnalysis,
    AnalysisResult,
    UploadedDocument,
    RadiologyFinding,
    IntegrationClient,
    AuditEvent,
)
from backend.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def init_database():
    """Initialize the database by creating all tables."""
    logger.info("Initializing ClaraMed database...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Created tables: {', '.join(tables)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
