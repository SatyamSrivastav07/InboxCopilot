from __future__ import annotations

import logging

from redis import Redis
from redis.exceptions import RedisError

from app.config import Settings

logger = logging.getLogger(__name__)


class RateLimitExceededError(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__(f"Too many requests. Try again in {self.retry_after} seconds.")


class RateLimitUnavailableError(RuntimeError):
    """Raised in production when the shared limiter cannot reach Redis."""


class RateLimiter:
    """Small Redis fixed-window limiter for costly, authenticated operations."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    def enforce(self, *, bucket: str, user_id: int, limit: int, window_seconds: int) -> None:
        key = f"rate-limit:v1:{bucket}:user:{user_id}"
        try:
            count = int(self.redis.incr(key))
            if count == 1:
                self.redis.expire(key, window_seconds)
            if count > limit:
                retry_after = int(self.redis.ttl(key))
                raise RateLimitExceededError(retry_after if retry_after > 0 else window_seconds)
        except RateLimitExceededError:
            raise
        except RedisError as exc:
            if self.settings.app_env == "production":
                raise RateLimitUnavailableError("Rate limiting is temporarily unavailable.") from exc
            logger.warning("event=rate_limit_unavailable bucket=%s", bucket)
