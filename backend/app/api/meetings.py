from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import CurrentUser
from app.schemas.persistence import PersistedMeeting
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("", response_model=list[PersistedMeeting])
def list_meetings(
    _user: CurrentUser,
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[PersistedMeeting]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not exceed date_to.")
    return service.list_meetings(date_from=date_from, date_to=date_to)
