import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.schemas.search import (
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.schemas.jobs import JobQueued
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService
from app.vectorstore.dependencies import get_vector_retriever
from app.vectorstore.retriever import VectorRetriever
from app.core.metrics import log_timing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["semantic-search"])


@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    retriever: Annotated[VectorRetriever, Depends(get_vector_retriever)],
) -> SemanticSearchResponse:
    logger.info("Semantic search requested with top_k=%s", request.top_k)
    with log_timing(logger, "semantic_retrieval", top_k=request.top_k):
        results = retriever.search(
            request.query, top_k=request.top_k, filters=request.filters
        )
    return SemanticSearchResponse(results=[item.to_schema() for item in results])


@router.post("/reindex", response_model=JobQueued, status_code=202)
def reindex(
    request: Request,
    jobs: Annotated[JobService, Depends(get_job_service)],
) -> JobQueued:
    return jobs.enqueue(
        "app.workers.indexing_tasks.reindex_inbox",
        lock_key="lock:inbox-reindex",
        request_id=getattr(request.state, "request_id", None),
    )
