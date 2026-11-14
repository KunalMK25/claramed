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

# Create Celery app with Redis 3.x compatible URL
# Use sentinel:// scheme which forces older protocol compatibility
celery_app = Celery(
    "claramed",
)

# Set broker and backend separately to avoid RESP3 issues
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
    # Redis 3.x compatible transport options
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True,
        'max_connections': 10,
    },
    result_backend_transport_options={
        'max_connections': 10,
    },
    # Use Redis sentinel compatibility mode
    broker_use_ssl=False,
    redis_socket_timeout=5,
    redis_socket_connect_timeout=5,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["backend.workers"])

logger.info("Celery app configured")
