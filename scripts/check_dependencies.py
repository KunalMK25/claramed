"""
Dependency and Environment Validation Script

Validates that all required dependencies and services are available.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def check_python_version():
    """Check Python version."""
    import sys
    version = sys.version_info
    logger.info(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 11:
        logger.info("✓ Python version OK")
        return True
    else:
        logger.error("✗ Python 3.11+ required")
        return False


def check_imports():
    """Check critical package imports."""
    checks = []
    
    packages = [
        ("streamlit", "Streamlit"),
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("alembic", "Alembic"),
        ("pydantic", "Pydantic"),
        ("langchain", "LangChain"),
        ("PyPDF2", "PyPDF2"),
        ("PIL", "Pillow"),
        ("torch", "PyTorch"),
        ("torchvision", "TorchVision"),
        ("torchxrayvision", "TorchXRayVision"),
        ("celery", "Celery"),
        ("redis", "Redis"),
    ]
    
    for module, name in packages:
        try:
            __import__(module)
            logger.info(f"✓ {name} available")
            checks.append(True)
        except ImportError as e:
            logger.error(f"✗ {name} not available: {str(e)}")
            checks.append(False)
    
    return all(checks)


def check_tesseract():
    """Check Tesseract OCR availability."""
    import subprocess
    
    try:
        result = subprocess.run(
            [settings.TESSERACT_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            logger.info(f"✓ Tesseract available: {version_line}")
            return True
        else:
            logger.error("✗ Tesseract command failed")
            return False
    except FileNotFoundError:
        logger.error(f"✗ Tesseract not found at: {settings.TESSERACT_CMD}")
        logger.info("  Install: https://github.com/tesseract-ocr/tesseract")
        return False
    except Exception as e:
        logger.error(f"✗ Tesseract check failed: {str(e)}")
        return False


def check_database():
    """Check database connectivity."""
    try:
        from backend.database.connection import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        logger.info("✓ Database connection OK")
        return True
        
    except Exception as e:
        logger.error(f"✗ Database connection failed: {str(e)}")
        logger.info(f"  Ensure PostgreSQL is running and DATABASE_URL is correct")
        logger.info(f"  Current: {settings.DATABASE_URL}")
        return False


def check_redis():
    """Check Redis connectivity."""
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        logger.info("✓ Redis connection OK")
        return True
        
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {str(e)}")
        logger.info(f"  Ensure Redis is running and REDIS_URL is correct")
        logger.info(f"  Current: {settings.REDIS_URL}")
        return False


def check_groq_api_key():
    """Check Groq API key configuration."""
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here":
        logger.info("✓ GROQ_API_KEY configured")
        return True
    else:
        logger.warning("⚠ GROQ_API_KEY not configured (LLM features will fail)")
        return False


def check_storage():
    """Check storage configuration."""
    if settings.STORAGE_PROVIDER == "local":
        storage_path = Path(settings.STORAGE_LOCAL_PATH)
        if not storage_path.exists():
            logger.info(f"Creating local storage directory: {storage_path}")
            storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✓ Local storage configured: {storage_path}")
        return True
    elif settings.STORAGE_PROVIDER == "s3":
        if settings.STORAGE_ACCESS_KEY and settings.STORAGE_SECRET_KEY:
            logger.info("✓ S3 storage credentials configured")
            return True
        else:
            logger.error("✗ S3 storage selected but credentials missing")
            return False
    else:
        logger.error(f"✗ Unknown storage provider: {settings.STORAGE_PROVIDER}")
        return False


def check_model_cache():
    """Check model cache directory."""
    cache_dir = Path(settings.RADIOLOGY_MODEL_CACHE_DIR)
    if not cache_dir.exists():
        logger.info(f"Creating model cache directory: {cache_dir}")
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"✓ Model cache directory: {cache_dir}")
    return True


def main():
    """Run all checks."""
    logger.info("=" * 60)
    logger.info("ClaraMed Dependency and Environment Validation")
    logger.info("=" * 60)
    
    checks = {
        "Python Version": check_python_version(),
        "Package Imports": check_imports(),
        "Tesseract OCR": check_tesseract(),
        "PostgreSQL Database": check_database(),
        "Redis": check_redis(),
        "Groq API Key": check_groq_api_key(),
        "Storage Configuration": check_storage(),
        "Model Cache": check_model_cache(),
    }
    
    logger.info("=" * 60)
    logger.info("Validation Summary")
    logger.info("=" * 60)
    
    for check_name, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {check_name}")
    
    logger.info("=" * 60)
    
    # Count critical vs non-critical failures
    critical_checks = ["Python Version", "Package Imports", "PostgreSQL Database"]
    critical_passed = all(checks[name] for name in critical_checks if name in checks)
    
    if critical_passed:
        logger.info("✓ All critical checks passed")
        logger.info("  Application can start (some features may be limited)")
        return 0
    else:
        logger.error("✗ Critical checks failed")
        logger.error("  Fix critical issues before starting the application")
        return 1


if __name__ == "__main__":
    sys.exit(main())
