from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.persistence import DashboardStats
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
def dashboard(
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
) -> DashboardStats:
    return service.dashboard()
