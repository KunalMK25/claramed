"""
Celery Application Configuration

Configures Celery for background task processing.
Compatible with Redis 3.x on Windows.
"""
from celery import Celery
from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "claramed",
)

# Set broker and backend URLs
celery_app.conf.broker_url = settings.REDIS_URL
celery_app.conf.result_backend = settings.REDIS_URL

# Configure Celery with Redis 3.x compatibility
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
    broker_connection_retry_on_startup=True,
    # Redis 8.x with RESP2 protocol for Redis 3.x compatibility
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
        'max_connections': 10,
        'connection_kwargs': {
            'protocol': 2,  # Force RESP2
        }
    },
    result_backend_transport_options={
        'max_connections': 10,
        'connection_kwargs': {
            'protocol': 2,  # Force RESP2
        }
    },
    # Use Redis sentinel compatibility mode
    broker_use_ssl=False,
    redis_socket_timeout=5,
    redis_socket_connect_timeout=5,
)

# Periodic maintenance (run with: celery -A backend.workers.celery_app beat)
celery_app.conf.beat_schedule = {
    "purge-expired-results": {
        "task": "backend.workers.callbacks.purge_expired_results",
        "schedule": 3600.0,
    },
    "sweep-stale-jobs": {
        "task": "backend.workers.callbacks.sweep_stale_jobs_task",
        "schedule": 600.0,
    },
}

# Auto-discover tasks (tasks.py by default, plus callbacks.py)
celery_app.autodiscover_tasks(["backend.workers"])
celery_app.autodiscover_tasks(["backend.workers"], related_name="callbacks")

logger.info("Celery app configured")
