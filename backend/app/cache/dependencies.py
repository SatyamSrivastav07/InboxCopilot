from functools import lru_cache

from app.cache.client import get_redis_client
from app.cache.service import CacheService


@lru_cache
def get_cache_service() -> CacheService:
    return CacheService(get_redis_client())
