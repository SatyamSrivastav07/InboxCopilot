from functools import lru_cache

from app.cache.client import get_redis_client
from app.services.jobs import JobService
from app.workers.celery_app import celery_app


@lru_cache
def get_job_service() -> JobService:
    return JobService(celery_app, get_redis_client())
