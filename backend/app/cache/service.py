from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from redis import Redis

from app.cache.keys import DASHBOARD_KEY, LEGACY_DASHBOARD_KEYS
from app.config import get_settings


def _json_default(value: object) -> str:
    """Serialize the temporal values returned by dashboard and query schemas."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class CacheService:
    def __init__(self, client: Redis, ttl_seconds: int | None = None) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds or get_settings().cache_ttl_seconds

    def get_json(self, key: str) -> Any | None:
        value = self.client.get(key)
        return json.loads(value) if value is not None else None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self.client.setex(
            key,
            ttl_seconds or self.ttl_seconds,
            json.dumps(value, default=_json_default),
        )

    def delete(self, *keys: str) -> None:
        if keys:
            self.client.delete(*keys)

    def invalidate_inbox_summaries(self) -> None:
        # Remove the prior schema key too, so upgrades cannot show stale dashboard data.
        self.delete(DASHBOARD_KEY, *LEGACY_DASHBOARD_KEYS)
