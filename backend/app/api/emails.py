from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.auth.dependencies import CurrentUser
from app.cache.keys import email_reprocess_lock_key
from app.schemas.email import EmailCategory, Priority
from app.schemas.persistence import PersistedEmail
from app.schemas.jobs import JobQueued, JobState
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService
from app.services.inline_jobs import run_inline_reprocess
from app.config import get_settings
from app.security.rate_limit_dependencies import limit_inbox_sync

router = APIRouter(prefix="/api/emails", tags=["persisted-emails"])


@router.get("", response_model=list[PersistedEmail])
def list_emails(
    _user: CurrentUser,
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    category: EmailCategory | None = Query(default=None),
    priority: Priority | None = Query(default=None),
    reply_required: bool | None = Query(default=None),
) -> list[PersistedEmail]:
    return service.list_emails(
        limit=limit,
        offset=offset,
        category=category.value if category else None,
        priority=priority.value if priority else None,
        reply_required=reply_required,
    )


@router.get("/{email_id}", response_model=PersistedEmail)
def get_email(
    email_id: int,
    _user: CurrentUser,
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
) -> PersistedEmail:
    return service.get_email(email_id)


@router.post("/{email_id}/reprocess", response_model=JobQueued | JobState, status_code=202)
def reprocess_email(
    email_id: int,
    request: Request,
    response: Response,
    user: CurrentUser,
    _rate_limit: Annotated[None, Depends(limit_inbox_sync)],
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    jobs: Annotated[JobService, Depends(get_job_service)],
) -> JobQueued | JobState:
    service.get_email(email_id)
    if get_settings().sync_execution_mode == "request":
        response.status_code = status.HTTP_200_OK
        return run_inline_reprocess(user_id=user.id, email_id=email_id)
    return jobs.enqueue(
        "app.workers.gmail_tasks.reprocess_email",
        kwargs={"user_id": user.id, "email_id": email_id},
        lock_key=email_reprocess_lock_key(user.id, email_id),
        user_id=user.id,
        request_id=getattr(request.state, "request_id", None),
    )
