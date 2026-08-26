from __future__ import annotations

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import Settings
from app.security.rate_limit import RateLimitExceededError, RateLimiter, RateLimitUnavailableError


class FakeRedis:
    def __init__(self):
        self.data: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def expire(self, key, seconds):
        self.expiries[key] = seconds

    def ttl(self, key):
        return self.expiries.get(key, -1)


def test_rate_limiter_is_scoped_to_user_and_returns_retry_time(tmp_path):
    redis = FakeRedis()
    limiter = RateLimiter(redis, Settings(chroma_persist_directory=tmp_path / "chroma"))

    limiter.enforce(bucket="sync", user_id=1, limit=1, window_seconds=60)
    limiter.enforce(bucket="sync", user_id=2, limit=1, window_seconds=60)

    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.enforce(bucket="sync", user_id=1, limit=1, window_seconds=60)
    assert exc_info.value.retry_after == 60


class BrokenRedis:
    def incr(self, _key):
        raise RedisConnectionError("offline")


def test_rate_limiter_fails_closed_in_production_and_open_in_development(tmp_path):
    production = RateLimiter(
        BrokenRedis(), Settings(app_env="production", chroma_persist_directory=tmp_path / "prod")
    )
    with pytest.raises(RateLimitUnavailableError):
        production.enforce(bucket="sync", user_id=1, limit=1, window_seconds=60)

    development = RateLimiter(
        BrokenRedis(), Settings(chroma_persist_directory=tmp_path / "dev")
    )
    development.enforce(bucket="sync", user_id=1, limit=1, window_seconds=60)
