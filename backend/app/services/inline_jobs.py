"""Run small, user-triggered inbox jobs without an always-on Celery worker.

Free web hosts commonly suspend idle services and do not provide a worker process.
This module intentionally supports only work initiated by the current browser request;
it is not a replacement for durable background processing.
"""

from __future__ import annotations

from uuid import uuid4

from redis.exceptions import RedisError

from app.cache.client import get_redis_client
from app.cache.service import CacheService
from app.config import get_settings
from app.database.session import get_session_factory
from app.genai.analyzer import get_email_analyzer
from app.gmail.client import build_gmail_client
from app.gmail.fetcher import GmailFetcher
from app.gmail.schemas import GmailSyncRequest
from app.gmail.user_auth import UserGmailAuthService
from app.schemas.jobs import JobState
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.services.reindex import ReindexService
from app.vectorstore.dependencies import get_vector_indexer


def run_inline_gmail_sync(*, user_id: int, request: GmailSyncRequest) -> JobState:
    """Synchronously analyze a deliberately small batch of the user's mail."""
    with get_session_factory()() as db:
        service = _gmail_sync_service(db, user_id)
        summary = service.sync_background(request)
    _invalidate_dashboard_cache(user_id)
    return _job_state(summary)


def run_inline_reprocess(*, user_id: int, email_id: int) -> JobState:
    with get_session_factory()() as db:
        result = _gmail_sync_service(db, user_id).reprocess(email_id)
    _invalidate_dashboard_cache(user_id)
    return _job_state(result)


def run_inline_reindex(*, user_id: int) -> JobState:
    with get_session_factory()() as db:
        result = ReindexService(db, get_vector_indexer(), user_id).reindex_background(None)
    return _job_state(result)


def _gmail_sync_service(db, user_id: int) -> GmailSyncService:
    auth = UserGmailAuthService(db, user_id, get_settings())
    return GmailSyncService(
        GmailFetcher(lambda: build_gmail_client(auth)),
        get_email_analyzer(),
        EmailPersistenceService(db, user_id),
        get_vector_indexer(),
    )


def _invalidate_dashboard_cache(user_id: int) -> None:
    try:
        CacheService(get_redis_client()).invalidate_inbox_summaries(user_id)
    except RedisError:
        # Caching is an optimization; a completed inline sync must remain usable.
        return


def _job_state(summary: dict[str, object]) -> JobState:
    return JobState(
        job_id=f"inline-{uuid4()}",
        status=summary["status"],
        progress=summary.get("progress", {}),
        result=summary.get("result"),
        failed=summary.get("failed", []),
        error=("Inbox processing failed. Please try again." if summary["status"] == "failed" else None),
    )
