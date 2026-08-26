from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.schemas.email import EmailCategory, Priority
from app.schemas.persistence import PersistedEmail
from app.schemas.jobs import JobQueued
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService

router = APIRouter(prefix="/api/emails", tags=["persisted-emails"])


@router.get("", response_model=list[PersistedEmail])
def list_emails(
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
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
) -> PersistedEmail:
    return service.get_email(email_id)


@router.post("/{email_id}/reprocess", response_model=JobQueued, status_code=202)
def reprocess_email(
    email_id: int,
    request: Request,
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    jobs: Annotated[JobService, Depends(get_job_service)],
) -> JobQueued:
    service.get_email(email_id)
    return jobs.enqueue(
        "app.workers.gmail_tasks.reprocess_email",
        kwargs={"email_id": email_id},
        lock_key=f"lock:email-reprocess:{email_id}",
        request_id=getattr(request.state, "request_id", None),
    )
