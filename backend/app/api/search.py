import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.search import (
    ReindexResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.dependencies import get_reindex_service
from app.services.reindex import ReindexService
from app.vectorstore.dependencies import get_vector_retriever
from app.vectorstore.retriever import VectorRetriever

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["semantic-search"])


@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    retriever: Annotated[VectorRetriever, Depends(get_vector_retriever)],
) -> SemanticSearchResponse:
    logger.info("Semantic search requested with top_k=%s", request.top_k)
    results = retriever.search(
        request.query, top_k=request.top_k, filters=request.filters
    )
    return SemanticSearchResponse(results=[item.to_schema() for item in results])


@router.post("/reindex", response_model=ReindexResponse)
def reindex(
    service: Annotated[ReindexService, Depends(get_reindex_service)],
) -> ReindexResponse:
    return service.reindex_all()

