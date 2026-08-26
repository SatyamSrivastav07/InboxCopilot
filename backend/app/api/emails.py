from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.schemas.email import EmailCategory, Priority
from app.schemas.persistence import PersistedEmail
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService

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

