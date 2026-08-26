from typing import Annotated

from fastapi import APIRouter, Depends
from redis.exceptions import RedisError

from app.auth.dependencies import CurrentUser
from app.cache.dependencies import get_cache_service
from app.cache.service import CacheService
from app.schemas.draft import DraftSendResponse, DraftUpdate, ReplyDraft, ReplyDraftRequest
from app.services.dependencies import get_reply_service
from app.services.reply_service import ReplyService
from app.security.rate_limit_dependencies import limit_reply_generation

router = APIRouter(prefix="/api", tags=["reply-drafts"])


@router.post("/emails/{email_id}/draft-reply", response_model=ReplyDraft)
def generate_reply_draft(
    email_id: int,
    request: ReplyDraftRequest,
    _user: CurrentUser,
    _rate_limit: Annotated[None, Depends(limit_reply_generation)],
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.generate(email_id, request)


@router.get("/drafts/{draft_id}", response_model=ReplyDraft)
def get_reply_draft(
    draft_id: int,
    _user: CurrentUser,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.get(draft_id)


@router.patch("/drafts/{draft_id}", response_model=ReplyDraft)
def edit_reply_draft(
    draft_id: int,
    request: DraftUpdate,
    _user: CurrentUser,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.update(draft_id, request.body)


@router.post("/drafts/{draft_id}/approve", response_model=ReplyDraft)
def approve_reply_draft(
    draft_id: int,
    _user: CurrentUser,
    service: Annotated[ReplyService, Depends(get_reply_service)],
) -> ReplyDraft:
    return service.approve(draft_id)


@router.post("/drafts/{draft_id}/send", response_model=DraftSendResponse)
def send_reply_draft(
    draft_id: int,
    user: CurrentUser,
    service: Annotated[ReplyService, Depends(get_reply_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DraftSendResponse:
    result = service.send(draft_id)
    try:
        cache.invalidate_inbox_summaries(user.id)
    except RedisError:
        pass
    return result
