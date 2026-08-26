from __future__ import annotations

import json
from typing import Any

from redis import Redis

from app.cache.keys import DASHBOARD_KEY
from app.config import get_settings


class CacheService:
    def __init__(self, client: Redis, ttl_seconds: int | None = None) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds or get_settings().cache_ttl_seconds

    def get_json(self, key: str) -> Any | None:
        value = self.client.get(key)
        return json.loads(value) if value is not None else None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self.client.setex(key, ttl_seconds or self.ttl_seconds, json.dumps(value))

    def delete(self, *keys: str) -> None:
        if keys:
            self.client.delete(*keys)

    def invalidate_inbox_summaries(self) -> None:
        self.delete(DASHBOARD_KEY)
