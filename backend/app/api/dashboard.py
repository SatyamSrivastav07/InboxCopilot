from typing import Annotated

from fastapi import APIRouter, Depends
from redis.exceptions import RedisError

from app.cache.dependencies import get_cache_service
from app.cache.keys import DASHBOARD_KEY
from app.cache.service import CacheService
from app.schemas.persistence import DashboardStats
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
def dashboard(
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DashboardStats:
    try:
        cached = cache.get_json(DASHBOARD_KEY)
        if cached is not None:
            return DashboardStats.model_validate(cached)
    except RedisError:
        pass
    result = service.dashboard()
    try:
        cache.set_json(DASHBOARD_KEY, result.model_dump())
    except RedisError:
        pass
    return result
