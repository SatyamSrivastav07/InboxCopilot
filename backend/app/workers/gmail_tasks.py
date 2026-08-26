from __future__ import annotations

import logging
from redis.exceptions import RedisError

from app.cache.client import get_redis_client
from app.cache.keys import SYNC_LOCK_KEY
from app.cache.service import CacheService
from app.database.session import get_session_factory
from app.genai.analyzer import get_email_analyzer
from app.gmail.dependencies import get_gmail_fetcher
from app.gmail.schemas import GmailSyncRequest
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.vectorstore.dependencies import get_vector_indexer
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _request_id(task) -> str:
    return str((getattr(task.request, "headers", None) or {}).get("request_id") or "")


@celery_app.task(bind=True, name="app.workers.gmail_tasks.sync_gmail")
def sync_gmail(self, limit: int, unread_only: bool = False) -> dict[str, object]:
    job_id = self.request.id
    request_id = _request_id(self)
    logger.info("event=gmail_sync_started job_id=%s request_id=%s", job_id, request_id)

    def progress(total: int, processed: int, failed: int, failed_items: list[dict]) -> None:
        self.update_state(
            state="STARTED",
            meta={
                "progress": {"total": total, "processed": processed, "failed": failed},
                "failed": failed_items,
            },
        )

    try:
        with get_session_factory()() as db:
            service = GmailSyncService(
                get_gmail_fetcher(),
                get_email_analyzer(),
                EmailPersistenceService(db),
                get_vector_indexer(),
            )
            summary = service.sync_background(
                GmailSyncRequest(limit=limit, unread_only=unread_only),
                progress_callback=progress,
            )
        try:
            CacheService(get_redis_client()).invalidate_inbox_summaries()
        except RedisError:
            logger.warning("event=cache_invalidation_failed job_id=%s", job_id)
        logger.info("event=gmail_sync_finished job_id=%s status=%s", job_id, summary["status"])
        return summary
    finally:
        try:
            client = get_redis_client()
            if client.get(SYNC_LOCK_KEY) == job_id:
                client.delete(SYNC_LOCK_KEY)
        except RedisError:
            logger.warning("event=sync_lock_release_failed job_id=%s", job_id)


@celery_app.task(bind=True, name="app.workers.gmail_tasks.reprocess_email")
def reprocess_email(self, email_id: int) -> dict[str, object]:
    self.update_state(state="STARTED", meta={"progress": {"total": 1, "processed": 0, "failed": 0}})
    with get_session_factory()() as db:
        service = GmailSyncService(
            get_gmail_fetcher(),
            get_email_analyzer(),
            EmailPersistenceService(db),
            get_vector_indexer(),
        )
        result = service.reprocess(email_id)
    try:
        CacheService(get_redis_client()).invalidate_inbox_summaries()
    except RedisError:
        logger.warning("event=cache_invalidation_failed job_id=%s", self.request.id)
    return result
