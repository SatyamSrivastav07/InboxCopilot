from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.genai.analyzer import EmailAnalyzer, get_email_analyzer
from app.gmail.dependencies import get_gmail_fetcher
from app.gmail.fetcher import GmailFetcher
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.services.inbox_queries import InboxQueryService
from app.services.reindex import ReindexService
from app.vectorstore.dependencies import get_vector_indexer
from app.vectorstore.indexer import VectorIndexer


def get_inbox_query_service(
    db: Annotated[Session, Depends(get_db)],
) -> InboxQueryService:
    return InboxQueryService(db)


def get_gmail_sync_service(
    db: Annotated[Session, Depends(get_db)],
    fetcher: Annotated[GmailFetcher, Depends(get_gmail_fetcher)],
    analyzer: Annotated[EmailAnalyzer, Depends(get_email_analyzer)],
    indexer: Annotated[VectorIndexer, Depends(get_vector_indexer)],
) -> GmailSyncService:
    return GmailSyncService(fetcher, analyzer, EmailPersistenceService(db), indexer)


def get_reindex_service(
    db: Annotated[Session, Depends(get_db)],
    indexer: Annotated[VectorIndexer, Depends(get_vector_indexer)],
) -> ReindexService:
    return ReindexService(db, indexer)
