import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.auth.dependencies import CurrentUser
from app.cache.keys import inbox_reindex_lock_key
from app.schemas.search import (
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.schemas.jobs import JobQueued, JobState
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService
from app.vectorstore.dependencies import get_vector_retriever
from app.vectorstore.retriever import VectorRetriever
from app.core.metrics import log_timing
from app.config import get_settings
from app.services.inline_jobs import run_inline_reindex

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["semantic-search"])


@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    user: CurrentUser,
    retriever: Annotated[VectorRetriever, Depends(get_vector_retriever)],
) -> SemanticSearchResponse:
    logger.info("Semantic search requested with top_k=%s", request.top_k)
    with log_timing(logger, "semantic_retrieval", top_k=request.top_k):
        results = retriever.search(
            request.query, top_k=request.top_k, filters=request.filters, user_id=user.id
        )
    return SemanticSearchResponse(results=[item.to_schema() for item in results])


@router.post("/reindex", response_model=JobQueued | JobState, status_code=202)
def reindex(
    request: Request,
    response: Response,
    user: CurrentUser,
    jobs: Annotated[JobService, Depends(get_job_service)],
) -> JobQueued | JobState:
    if get_settings().sync_execution_mode == "request":
        response.status_code = status.HTTP_200_OK
        return run_inline_reindex(user_id=user.id)
    return jobs.enqueue(
        "app.workers.indexing_tasks.reindex_inbox",
        kwargs={"user_id": user.id},
        lock_key=inbox_reindex_lock_key(user.id),
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
    )
