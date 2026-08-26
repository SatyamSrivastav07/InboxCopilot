from __future__ import annotations

import base64
import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.cache.service import CacheService
from app.core.retry import call_with_retry
from app.database.dependencies import get_db
from app.gmail.errors import GmailMessageNotFoundError, GmailRateLimitError
from app.gmail.schemas import GmailSyncRequest
from app.main import app
from app.schemas.jobs import JobQueued
from app.schemas.email import EmailAnalysis
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.services.inbox_queries import InboxQueryService
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    def setex(self, key, ttl, value):
        self.values[key] = str(value)

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)

    def exists(self, key):
        return key in self.values

    def ping(self):
        return True


class FakeAsyncResult:
    def __init__(self, state="PENDING", info=None, result=None):
        self.state = state
        self.info = info
        self.result = result


class FakeCelery:
    def __init__(self):
        self.results = {}
        self.sent = []

    def AsyncResult(self, job_id):
        return self.results.get(job_id, FakeAsyncResult())

    def send_task(self, name, **options):
        self.sent.append((name, options))
        self.results[options["task_id"]] = FakeAsyncResult()


def gmail_payload(message_id: str, body: str):
    encoded = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1735689600000",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": f"Subject {message_id}"},
            ],
            "body": {"data": encoded},
        },
    }


class TwoMessageFetcher:
    def list_message_ids(self, limit, unread_only):
        return ["ok", "bad"]

    def fetch_message(self, message_id):
        return gmail_payload(message_id, "Please review this today.")


class OneFailureAnalyzer:
    def analyze(self, email):
        if email.subject.endswith("bad"):
            raise ValueError("permanent invalid provider output")
        return valid_analysis(email.sender, email.subject)


class SuccessfulIndexer:
    def index_email(self, email):
        return SimpleNamespace(chunks_created=1, skipped=False)


class QueueStub:
    def enqueue(self, task_name, **options):
        return JobQueued(job_id=f"job-{options['kwargs']['email_id']}")


def valid_analysis(sender: str, subject: str) -> EmailAnalysis:
    return EmailAnalysis(
        sender=sender,
        subject=subject,
        summary="Review is requested today.",
        classification={
            "category": "action_required",
            "priority": "high",
            "reason": "A review is requested.",
        },
        tasks=[],
        meeting=None,
        entities={"people": [], "organizations": [], "dates": ["today"], "locations": []},
        reply_required=False,
    )


def test_duplicate_sync_returns_existing_running_job():
    redis = FakeRedis()
    celery = FakeCelery()
    jobs = JobService(celery, redis)
    first = jobs.enqueue("sync", lock_key="lock:sync")
    second = jobs.enqueue("sync", lock_key="lock:sync")
    assert second.job_id == first.job_id
    assert second.reused is True
    assert len(celery.sent) == 1


def test_job_status_endpoint_reports_progress():
    redis = FakeRedis()
    celery = FakeCelery()
    redis.setex("job:known:abc", 60, "1")
    celery.results["abc"] = FakeAsyncResult(
        state="STARTED",
        info={"progress": {"total": 20, "processed": 8, "failed": 1}},
    )
    app.dependency_overrides[get_job_service] = lambda: JobService(celery, redis)
    try:
        response = TestClient(app).get("/api/jobs/abc")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["progress"] == {"total": 20, "processed": 8, "failed": 1}


def test_retry_retries_transient_but_not_permanent_errors():
    calls = []

    def transient_operation():
        calls.append("call")
        if len(calls) < 3:
            raise GmailRateLimitError("limited", retry_after=0)
        return "ok"

    assert call_with_retry(transient_operation, max_attempts=3, sleep=lambda _: None) == "ok"
    assert len(calls) == 3

    permanent_calls = []

    def permanent_operation():
        permanent_calls.append("call")
        raise GmailMessageNotFoundError("deleted")

    with pytest.raises(GmailMessageNotFoundError):
        call_with_retry(permanent_operation, max_attempts=3, sleep=lambda _: None)
    assert len(permanent_calls) == 1


def test_background_sync_returns_partial_success_and_persists_failure(db_session):
    progress = []
    service = GmailSyncService(
        TwoMessageFetcher(),
        OneFailureAnalyzer(),
        EmailPersistenceService(db_session),
        SuccessfulIndexer(),
    )
    result = service.sync_background(
        GmailSyncRequest(limit=5),
        progress_callback=lambda *values: progress.append(values),
    )
    assert result["status"] == "partial_success"
    assert result["result"] == {"total": 2, "cached": 0, "processed": 1, "failed": 1}
    failed = EmailPersistenceService(db_session).get_by_gmail_message_id("bad")
    assert failed.processing_status == "failed"
    assert failed.processing_error == "Analysis failed after retries."
    assert progress[-1][1:3] == (2, 1)


def test_pending_insert_is_idempotent_under_duplicate_message_id(db_session):
    from app.gmail.parser import parse_gmail_message

    email = parse_gmail_message(gmail_payload("same", "body"))
    persistence = EmailPersistenceService(db_session)
    first = persistence.create_pending_email(email)
    second = persistence.create_pending_email(email)
    assert first.created is True
    assert second.created is False
    assert first.email.id == second.email.id


def test_email_reprocess_endpoint_queues_job(db_session, override_db):
    from app.gmail.parser import parse_gmail_message

    gmail = parse_gmail_message(gmail_payload("reprocess", "Please review today."))
    saved = EmailPersistenceService(db_session).save_analyzed_email(
        gmail, valid_analysis(gmail.sender, gmail.subject)
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_job_service] = lambda: QueueStub()
    try:
        response = TestClient(app).post(f"/api/emails/{saved.email.id}/reprocess")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 202
    assert response.json()["job_id"] == f"job-{saved.email.id}"


def test_cache_get_set_and_dashboard_invalidation():
    redis = FakeRedis()
    cache = CacheService(redis, ttl_seconds=60)
    cache.set_json("cache:dashboard:v1", {"total_emails": 2})
    assert cache.get_json("cache:dashboard:v1") == {"total_emails": 2}
    cache.invalidate_inbox_summaries()
    assert cache.get_json("cache:dashboard:v1") is None


def test_health_and_readiness_check_database_and_redis(monkeypatch):
    main_module = importlib.import_module("app.main")

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement):
            return 1

    class Engine:
        def connect(self):
            return Connection()

    monkeypatch.setattr(main_module, "get_engine", lambda: Engine())
    monkeypatch.setattr(main_module, "get_redis_client", lambda: FakeRedis())
    client = TestClient(app)
    health = client.get("/health")
    readiness = client.get("/health/ready")
    assert health.status_code == 200
    assert health.headers["x-request-id"]
    assert readiness.status_code == 200
    assert readiness.json() == {
        "status": "ready",
        "dependencies": {"postgresql": "ok", "redis": "ok"},
    }
