from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.config import get_settings
from app.database.dependencies import get_db
from app.genai.analyzer import EmailAnalyzer, get_email_analyzer
from app.genai.inbox_workflow import InboxQueryWorkflow
from app.genai.query_router import QueryRouter
from app.genai.rag import InboxRAG
from app.genai.reply_chain import ReplyDraftGenerator
from app.gmail.dependencies import get_gmail_fetcher, get_gmail_sender
from app.gmail.fetcher import GmailFetcher
from app.gmail.sender import GmailSender
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.services.inbox_queries import InboxQueryService
from app.services.reindex import ReindexService
from app.services.reply_service import ReplyService
from app.services.structured_query_service import StructuredQueryService
from app.services.thread_context_service import ThreadContextService
from app.vectorstore.dependencies import get_vector_indexer, get_vector_retriever
from app.vectorstore.indexer import VectorIndexer
from app.vectorstore.retriever import VectorRetriever


def get_inbox_query_service(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> InboxQueryService:
    return InboxQueryService(db, user.id)


def get_gmail_sync_service(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    fetcher: Annotated[GmailFetcher, Depends(get_gmail_fetcher)],
    analyzer: Annotated[EmailAnalyzer, Depends(get_email_analyzer)],
    indexer: Annotated[VectorIndexer, Depends(get_vector_indexer)],
) -> GmailSyncService:
    return GmailSyncService(fetcher, analyzer, EmailPersistenceService(db, user.id), indexer)


def get_reindex_service(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    indexer: Annotated[VectorIndexer, Depends(get_vector_indexer)],
) -> ReindexService:
    return ReindexService(db, indexer, user.id)


@lru_cache
def get_query_router() -> QueryRouter:
    return QueryRouter(get_settings())


@lru_cache
def get_reply_draft_generator() -> ReplyDraftGenerator:
    return ReplyDraftGenerator(get_settings())


def get_reply_service(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    fetcher: Annotated[GmailFetcher, Depends(get_gmail_fetcher)],
    sender: Annotated[GmailSender, Depends(get_gmail_sender)],
    generator: Annotated[
        ReplyDraftGenerator, Depends(get_reply_draft_generator)
    ],
) -> ReplyService:
    return ReplyService(
        db,
        ThreadContextService(db, fetcher, get_settings(), user.id),
        generator,
        sender,
        user.id,
    )


def get_inbox_query_workflow(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
    retriever: Annotated[VectorRetriever, Depends(get_vector_retriever)],
    router: Annotated[QueryRouter, Depends(get_query_router)],
    reply_service: Annotated[ReplyService, Depends(get_reply_service)],
) -> InboxQueryWorkflow:
    return InboxQueryWorkflow(
        router,
        StructuredQueryService(db, user.id),
        InboxRAG(retriever, get_settings(), user_id=user.id),
        get_settings(),
        reply_service=reply_service,
    )
