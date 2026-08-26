from celery import Celery

from app.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging()

celery_app = Celery(
    "ai_inbox_copilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.gmail_tasks",
        "app.workers.indexing_tasks",
        "app.workers.maintenance_tasks",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=24 * 60 * 60,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    timezone="Asia/Kolkata",
)
