from typing import Annotated

from fastapi import APIRouter, Depends
from redis.exceptions import RedisError

from app.cache.dependencies import get_cache_service
from app.cache.service import CacheService
from app.schemas.draft import DraftSendResponse, DraftUpdate, ReplyDraft, ReplyDraftRequest
from app.services.dependencies import get_reply_service
from app.services.reply_service import ReplyService

router = APIRouter(prefix="/api", tags=["reply-drafts"])


@router.post("/emails/{email_id}/draft-reply", response_model=ReplyDraft)
def generate_reply_draft(
    email_id: int,
    request: ReplyDraftRequest,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.generate(email_id, request)


@router.get("/drafts/{draft_id}", response_model=ReplyDraft)
def get_reply_draft(
    draft_id: int,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.get(draft_id)


@router.patch("/drafts/{draft_id}", response_model=ReplyDraft)
def edit_reply_draft(
    draft_id: int,
    request: DraftUpdate,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.update(draft_id, request.body)


@router.post("/drafts/{draft_id}/approve", response_model=ReplyDraft)
def approve_reply_draft(
    draft_id: int,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.approve(draft_id)


@router.post("/drafts/{draft_id}/send", response_model=DraftSendResponse)
def send_reply_draft(
    draft_id: int,
    service: Annotated[ReplyService, Depends(get_reply_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DraftSendResponse:
    result = service.send(draft_id)
    try:
        cache.invalidate_inbox_summaries()
    except RedisError:
        pass
    return result
