from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import CurrentUser
from app.cache.client import get_redis_client
from app.config import get_settings
from app.security.rate_limit import RateLimiter


@lru_cache
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis_client(), get_settings())


def limit_manual_analysis(
    user: CurrentUser,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    limiter.enforce(bucket="manual-analysis", user_id=user.id, limit=15, window_seconds=3600)


def limit_inbox_sync(
    user: CurrentUser,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    limiter.enforce(bucket="inbox-sync", user_id=user.id, limit=6, window_seconds=3600)


def limit_reply_generation(
    user: CurrentUser,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    limiter.enforce(bucket="reply-generation", user_id=user.id, limit=20, window_seconds=3600)


def limit_inbox_assistant(
    user: CurrentUser,
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    limiter.enforce(bucket="inbox-assistant", user_id=user.id, limit=60, window_seconds=3600)
