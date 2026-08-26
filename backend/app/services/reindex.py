from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError
from app.database.repositories.email_repository import EmailRepository
from app.schemas.search import ReindexResponse
from app.vectorstore.indexer import VectorIndexer

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

