"""
Celery Application Configuration

Configures Celery for background task processing.
"""
from celery import Celery
from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "claramed",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.ANALYSIS_TIMEOUT_SECONDS,
    task_soft_time_limit=settings.ANALYSIS_TIMEOUT_SECONDS - 10,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["backend.workers"])

logger.info("Celery app configured")
