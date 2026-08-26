from __future__ import annotations

from time import time
from uuid import uuid4

from celery import Celery
from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings
from app.schemas.jobs import FailedJobItem, JobProgress, JobQueued, JobState


class JobQueueUnavailableError(RuntimeError):
    """Raised when Redis/Celery cannot accept or inspect work."""


class JobNotFoundError(RuntimeError):
    """Raised when a job identifier is unknown or expired."""


ACTIVE_STATES = {"PENDING", "RECEIVED", "STARTED", "RETRY"}
JOB_KNOWN_TTL_SECONDS = 24 * 60 * 60


def _queued_timestamp_key(job_id: str) -> str:
    return f"job:queued-at:{job_id}"


def _owner_key(job_id: str) -> str:
    return f"job:owner:{job_id}"


class JobService:
    def __init__(self, celery: Celery, redis: Redis) -> None:
        self.celery = celery
        self.redis = redis

    def enqueue(
        self,
        task_name: str,
        *,
        kwargs: dict[str, object] | None = None,
        lock_key: str | None = None,
        request_id: str | None = None,
        user_id: int | None = None,
    ) -> JobQueued:
        try:
            if lock_key:
                existing_id = self.redis.get(lock_key)
                if existing_id and self._can_reuse_locked_job(existing_id):
                    return JobQueued(job_id=existing_id, reused=True)
                if existing_id:
                    self._discard_stale_job(lock_key, existing_id)

            job_id = str(uuid4())
            if lock_key and not self.redis.set(
                lock_key,
                job_id,
                nx=True,
                ex=get_settings().sync_lock_ttl_seconds,
            ):
                existing_id = self.redis.get(lock_key)
                if existing_id:
                    return JobQueued(job_id=existing_id, reused=True)
                raise JobQueueUnavailableError("Could not acquire the background job lock.")
            try:
                self.redis.setex(f"job:known:{job_id}", JOB_KNOWN_TTL_SECONDS, "1")
                self.redis.setex(_queued_timestamp_key(job_id), JOB_KNOWN_TTL_SECONDS, str(time()))
                if user_id is not None:
                    self.redis.setex(_owner_key(job_id), JOB_KNOWN_TTL_SECONDS, str(user_id))
                self.celery.send_task(
                    task_name,
                    kwargs=kwargs or {},
                    task_id=job_id,
                    headers={"request_id": request_id or ""},
                )
            except Exception:
                self.redis.delete(
                    f"job:known:{job_id}", _queued_timestamp_key(job_id), _owner_key(job_id)
                )
                if lock_key:
                    self._release_owned_lock(lock_key, job_id)
                raise
            return JobQueued(job_id=job_id)
        except JobQueueUnavailableError:
            raise
        except (RedisError, OSError, ConnectionError) as exc:
            raise JobQueueUnavailableError(
                "Background processing is unavailable because Redis cannot be reached."
            ) from exc
        except Exception as exc:
            raise JobQueueUnavailableError("The background job could not be queued.") from exc

    def status(self, job_id: str, *, user_id: int | None = None) -> JobState:
        if user_id is not None:
            try:
                owner_id = self.redis.get(_owner_key(job_id))
            except RedisError as exc:
                raise JobQueueUnavailableError("The job status service is unavailable.") from exc
            if owner_id != str(user_id):
                raise JobNotFoundError("Background job was not found or has expired.")
        try:
            result = self.celery.AsyncResult(job_id)
            state = result.state
            info = result.info if isinstance(result.info, dict) else {}
        except Exception as exc:
            raise JobQueueUnavailableError("The job status service is unavailable.") from exc

        if state == "PENDING" and not info:
            try:
                if not self.redis.exists(f"job:known:{job_id}"):
                    raise JobNotFoundError("Background job was not found or has expired.")
            except JobNotFoundError:
                raise
            except RedisError as exc:
                raise JobQueueUnavailableError("The job status service is unavailable.") from exc
            return JobState(job_id=job_id, status="queued")
        if state in {"RECEIVED", "STARTED", "RETRY"}:
            return JobState(
                job_id=job_id,
                status="running",
                progress=JobProgress.model_validate(info.get("progress", {})),
                failed=[FailedJobItem.model_validate(item) for item in info.get("failed", [])],
            )
        if state == "SUCCESS":
            payload = result.result if isinstance(result.result, dict) else {}
            status = payload.get("status", "completed")
            return JobState(
                job_id=job_id,
                status=status,
                progress=JobProgress.model_validate(payload.get("progress", {})),
                result=payload.get("result"),
                failed=[FailedJobItem.model_validate(item) for item in payload.get("failed", [])],
            )
        if state == "FAILURE":
            return JobState(
                job_id=job_id,
                status="failed",
                error="Background processing failed. Check worker logs with this job ID.",
                progress=JobProgress.model_validate(info.get("progress", {})),
            )
        return JobState(job_id=job_id, status="queued")

    def _release_owned_lock(self, lock_key: str, job_id: str) -> None:
        if self.redis.get(lock_key) == job_id:
            self.redis.delete(lock_key)

    def _can_reuse_locked_job(self, job_id: str) -> bool:
        state = self.celery.AsyncResult(job_id).state
        if state not in ACTIVE_STATES:
            return False
        if state != "PENDING":
            return True
        queued_at = self.redis.get(_queued_timestamp_key(job_id))
        if queued_at is None:
            return False
        try:
            return time() - float(queued_at) < get_settings().queued_job_stale_seconds
        except (TypeError, ValueError):
            return False

    def _discard_stale_job(self, lock_key: str, job_id: str) -> None:
        """Release a job that never reached a worker, including pre-upgrade jobs."""
        self.redis.delete(
            lock_key, f"job:known:{job_id}", _queued_timestamp_key(job_id), _owner_key(job_id)
        )
