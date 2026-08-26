from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError
from app.database.repositories.email_repository import EmailRepository
from app.schemas.search import ReindexResponse
from app.vectorstore.indexer import VectorIndexer
from app.core.retry import call_with_retry

logger = logging.getLogger(__name__)


class ReindexService:
    def __init__(self, db: Session, indexer: VectorIndexer) -> None:
        self.emails = EmailRepository(db)
        self.indexer = indexer

    def reindex_all(self) -> ReindexResponse:
        try:
            emails = self.emails.list_all_for_indexing()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable or migrations have not been applied."
            ) from exc

        logger.info("Reindexing %s persisted emails", len(emails))
        self.indexer.store.clear()
        emails_indexed = 0
        chunks_created = 0
        for email in emails:
            result = self.indexer.reindex_email(email)
            emails_indexed += 1
            chunks_created += result.chunks_created
        logger.info("Reindex completed with %s chunks", chunks_created)
        return ReindexResponse(
            emails_indexed=emails_indexed,
            emails_skipped=0,
            chunks_created=chunks_created,
        )

    def reindex_background(
        self,
        progress_callback: Callable[[int, int, int, list[dict]], None] | None = None,
    ) -> dict[str, object]:
        try:
            emails = self.emails.list_all_for_indexing()
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable or migrations have not been applied."
            ) from exc
        total = len(emails)
        indexed = failed = chunks = 0
        failed_items: list[dict] = []
        if progress_callback:
            progress_callback(total, 0, 0, [])
        self.indexer.store.clear()
        for email in emails:
            try:
                email.vector_status = "pending"
                self.emails.db.commit()
                result = call_with_retry(lambda: self.indexer.reindex_email(email))
                email.vector_status = "indexed"
                self.emails.db.commit()
                indexed += 1
                chunks += result.chunks_created
            except Exception:
                self.emails.db.rollback()
                email.vector_status = "failed"
                self.emails.db.commit()
                failed += 1
                failed_items.append(
                    {"email_id": email.id, "reason": "Vector indexing failed after retries."}
                )
                logger.warning("event=reindex_email_failed email_id=%s", email.id, exc_info=True)
            if progress_callback:
                progress_callback(total, indexed + failed, failed, failed_items)
        status = "partial_success" if failed and indexed else "failed" if failed else "completed"
        return {
            "status": status,
            "progress": {"total": total, "processed": total, "failed": failed},
            "result": {
                "total": total,
                "emails_indexed": indexed,
                "emails_failed": failed,
                "chunks_created": chunks,
            },
            "failed": failed_items,
        }
