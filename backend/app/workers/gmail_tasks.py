from __future__ import annotations

import logging
from redis.exceptions import RedisError

from app.cache.client import get_redis_client
from app.cache.keys import SYNC_LOCK_KEY, gmail_sync_lock_key
from app.cache.service import CacheService
from app.config import get_settings
from app.database.session import get_session_factory
from app.genai.analyzer import get_email_analyzer
from app.gmail.auth import GmailAuthService
from app.gmail.client import build_gmail_client
from app.gmail.fetcher import GmailFetcher
from app.gmail.user_auth import UserGmailAuthService
from app.gmail.schemas import GmailSyncRequest
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.vectorstore.dependencies import get_vector_indexer
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _request_id(task) -> str:
    return str((getattr(task.request, "headers", None) or {}).get("request_id") or "")


@celery_app.task(bind=True, name="app.workers.gmail_tasks.sync_gmail")
def sync_gmail(
    self, limit: int, unread_only: bool = False, user_id: int | None = None
) -> dict[str, object]:
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
            auth = (
                UserGmailAuthService(db, user_id, get_settings())
                if user_id is not None
                else GmailAuthService(get_settings())
            )
            fetcher = GmailFetcher(lambda: build_gmail_client(auth))
            service = GmailSyncService(
                fetcher,
                get_email_analyzer(),
                EmailPersistenceService(db, user_id),
                get_vector_indexer(),
            )
            summary = service.sync_background(
                GmailSyncRequest(limit=limit, unread_only=unread_only),
                progress_callback=progress,
            )
        try:
            CacheService(get_redis_client()).invalidate_inbox_summaries(user_id)
        except RedisError:
            logger.warning("event=cache_invalidation_failed job_id=%s", job_id)
        logger.info("event=gmail_sync_finished job_id=%s status=%s", job_id, summary["status"])
        return summary
    finally:
        try:
            client = get_redis_client()
            lock_key = gmail_sync_lock_key(user_id) if user_id is not None else SYNC_LOCK_KEY
            if client.get(lock_key) == job_id:
                client.delete(lock_key)
        except RedisError:
            logger.warning("event=sync_lock_release_failed job_id=%s", job_id)


@celery_app.task(bind=True, name="app.workers.gmail_tasks.reprocess_email")
def reprocess_email(self, email_id: int, user_id: int | None = None) -> dict[str, object]:
    self.update_state(state="STARTED", meta={"progress": {"total": 1, "processed": 0, "failed": 0}})
    with get_session_factory()() as db:
        auth = (
            UserGmailAuthService(db, user_id, get_settings())
            if user_id is not None
            else GmailAuthService(get_settings())
        )
        fetcher = GmailFetcher(lambda: build_gmail_client(auth))
        service = GmailSyncService(
            fetcher,
            get_email_analyzer(),
            EmailPersistenceService(db, user_id),
            get_vector_indexer(),
        )
        result = service.reprocess(email_id)
    try:
        CacheService(get_redis_client()).invalidate_inbox_summaries(user_id)
    except RedisError:
        logger.warning("event=cache_invalidation_failed job_id=%s", self.request.id)
    return result
