from typing import Annotated

from fastapi import APIRouter, Depends
from redis.exceptions import RedisError

from app.auth.dependencies import CurrentUser
from app.cache.dependencies import get_cache_service
from app.cache.keys import dashboard_key
from app.cache.service import CacheService
from app.schemas.persistence import DashboardOverview
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOverview)
def dashboard(
    user: CurrentUser,
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DashboardOverview:
    try:
        cached = cache.get_json(dashboard_key(user.id))
        if cached is not None:
            return DashboardOverview.model_validate(cached)
    except RedisError:
        pass
    result = service.dashboard_overview()
    try:
        cache.set_json(dashboard_key(user.id), result.model_dump())
    except RedisError:
        pass
    return result
