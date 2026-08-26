from typing import Annotated

from fastapi import APIRouter, Depends

from app.genai.rag import InboxRAG
from app.schemas.search import AskInboxRequest, AskInboxResponse
from app.vectorstore.dependencies import get_inbox_rag

router = APIRouter(prefix="/api/chat", tags=["inbox-chat"])


@router.post("/inbox", response_model=AskInboxResponse)
def ask_inbox(
    request: AskInboxRequest,
    rag: Annotated[InboxRAG, Depends(get_inbox_rag)],
) -> AskInboxResponse:
    return rag.ask(
        request.question,
        top_k=request.top_k,
        filters=request.filters,
    )

