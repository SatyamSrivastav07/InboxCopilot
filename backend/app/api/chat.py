from typing import Annotated
import logging

from fastapi import APIRouter, Depends

from app.genai.inbox_workflow import InboxQueryWorkflow
from app.schemas.query import RoutedInboxRequest, RoutedInboxResponse
from app.services.dependencies import get_inbox_query_workflow
from app.core.metrics import log_timing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["inbox-chat"])


@router.post("/inbox", response_model=RoutedInboxResponse)
def ask_inbox(
    request: RoutedInboxRequest,
    workflow: Annotated[InboxQueryWorkflow, Depends(get_inbox_query_workflow)],
) -> RoutedInboxResponse:
    with log_timing(logger, "inbox_query_workflow"):
        return workflow.ask(
            request.question,
            top_k=request.top_k,
            filters=request.filters,
        )
