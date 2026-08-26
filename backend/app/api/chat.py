from typing import Annotated

from fastapi import APIRouter, Depends

from app.genai.inbox_workflow import InboxQueryWorkflow
from app.schemas.query import RoutedInboxRequest, RoutedInboxResponse
from app.services.dependencies import get_inbox_query_workflow

router = APIRouter(prefix="/api/chat", tags=["inbox-chat"])


@router.post("/inbox", response_model=RoutedInboxResponse)
def ask_inbox(
    request: RoutedInboxRequest,
    workflow: Annotated[InboxQueryWorkflow, Depends(get_inbox_query_workflow)],
) -> RoutedInboxResponse:
    return workflow.ask(
        request.question,
        top_k=request.top_k,
        filters=request.filters,
    )
