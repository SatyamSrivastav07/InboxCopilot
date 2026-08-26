from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.dependencies import get_db
from app.genai.analyzer import EmailAnalyzer, get_email_analyzer
from app.genai.inbox_workflow import InboxQueryWorkflow
from app.genai.query_router import QueryRouter
from app.genai.rag import InboxRAG
from app.gmail.dependencies import get_gmail_fetcher
from app.gmail.fetcher import GmailFetcher
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.services.inbox_queries import InboxQueryService
from app.services.reindex import ReindexService
from app.services.structured_query_service import StructuredQueryService
from app.vectorstore.dependencies import get_inbox_rag, get_vector_indexer
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


@lru_cache
def get_query_router() -> QueryRouter:
    return QueryRouter(get_settings())


def get_inbox_query_workflow(
    db: Annotated[Session, Depends(get_db)],
    rag: Annotated[InboxRAG, Depends(get_inbox_rag)],
    router: Annotated[QueryRouter, Depends(get_query_router)],
) -> InboxQueryWorkflow:
    return InboxQueryWorkflow(
        router,
        StructuredQueryService(db),
        rag,
        get_settings(),
    )
