import base64
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.genai.analyzer import get_email_analyzer
from app.config import Settings
from app.database.dependencies import get_db
from app.gmail.auth import GMAIL_READONLY_SCOPE, GMAIL_SCOPES, GMAIL_SEND_SCOPE, GmailAuthService
from app.gmail.dependencies import get_gmail_auth_service, get_gmail_fetcher
from app.gmail.parser import parse_gmail_message
from app.gmail.schemas import GmailSyncRequest
from app.main import app
from app.schemas.email import EmailAnalysis, EmailInput
from app.services.email_persistence import EmailPersistenceService
from app.services.gmail_sync import GmailSyncService
from app.services.job_dependencies import get_job_service
from app.schemas.jobs import JobQueued
from app.vectorstore.dependencies import get_vector_indexer
from app.vectorstore.indexer import IndexResult


def payload(message_id: str, body: str):
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
                {"name": "To", "value": "user@example.com"},
                {"name": "Subject", "value": f"Subject {message_id}"},
            ],
            "body": {"data": encoded} if body else {},
        },
    }


class StubFetcher:
    def list_message_ids(self, limit, unread_only):
        assert limit == 5
        assert unread_only is True
        return ["good", "empty", "provider-failure"]

    def fetch_message(self, message_id):
        return payload(message_id, "Please review this today." if message_id != "empty" else "")


class PartiallyFailingAnalyzer:
    def analyze(self, email):
        if "provider-failure" in email.subject:
            raise RuntimeError("provider unavailable")
        return EmailAnalysis(
            sender=email.sender,
            subject=email.subject,
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


class CachedFetcher:
    def list_message_ids(self, limit, unread_only):
        return ["cached"]

    def fetch_message(self, message_id):
        return payload(message_id, "Please review this today.")


class StubIndexer:
    def __init__(self):
        self.indexed_ids = []

    def index_email(self, email):
        self.indexed_ids.append(email.id)
        return IndexResult(email_id=email.id, chunks_created=1, skipped=False)


class ConnectedAuth:
    def get_credentials(self):
        return Mock(scopes=list(GMAIL_SCOPES))


class StubJobs:
    def __init__(self):
        self.calls = []

    def enqueue(self, task_name, **options):
        self.calls.append((task_name, options))
        return JobQueued(job_id="queued-job")


def test_gmail_scope_is_read_only():
    assert GMAIL_READONLY_SCOPE == "https://www.googleapis.com/auth/gmail.readonly"


def test_authorization_url_uses_minimal_read_and_send_scopes(tmp_path: Path):
    settings = Settings(
        mistral_api_key=None,
        mistral_model="mistral-small-latest",
        frontend_origins=("http://localhost:5173",),
        frontend_url="http://localhost:5173",
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="never-expose-this-secret",
        google_redirect_uri="http://localhost:8000/api/gmail/callback",
        gmail_token_file=tmp_path / "token.json",
        database_url=None,
    )
    auth_service = GmailAuthService(settings)
    authorization_url = auth_service.authorization_url()
    query = parse_qs(urlparse(authorization_url).query)

    granted = set(query["scope"][0].split())
    assert granted == set(GMAIL_SCOPES)
    assert GMAIL_READONLY_SCOPE in granted
    assert GMAIL_SEND_SCOPE in granted
    assert "https://www.googleapis.com/auth/gmail.modify" not in granted
    assert query["redirect_uri"] == [settings.google_redirect_uri]
    assert query["state"][0]
    assert query["code_challenge"][0]
    assert auth_service._pending_states[query["state"][0]][1]
    assert settings.google_client_secret not in authorization_url


def test_gmail_status_reports_read_and_send_capabilities():
    app.dependency_overrides[get_gmail_auth_service] = lambda: ConnectedAuth()
    try:
        response = TestClient(app).get("/api/gmail/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "connected": True,
        "can_read": True,
        "can_send": True,
    }


def test_sync_queues_background_job_instead_of_blocking():
    jobs = StubJobs()
    app.dependency_overrides[get_job_service] = lambda: jobs
    try:
        response = TestClient(app).post(
            "/api/gmail/sync", json={"limit": 5, "unread_only": True}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {"job_id": "queued-job", "status": "queued", "reused": False}
    assert jobs.calls[0][0] == "app.workers.gmail_tasks.sync_gmail"
    assert jobs.calls[0][1]["kwargs"] == {"limit": 5, "unread_only": True}


def test_sync_rejects_unbounded_limit(override_db):
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post(
            "/api/gmail/sync", json={"limit": 100, "unread_only": False}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_cached_sync_does_not_call_analyzer(db_session, override_db):
    parsed = parse_gmail_message(payload("cached", "Please review this today."))
    stored_analysis = PartiallyFailingAnalyzer().analyze(
        EmailInput(sender=parsed.sender, subject=parsed.subject, body=parsed.body)
    )
    EmailPersistenceService(db_session).save_analyzed_email(parsed, stored_analysis)
    analyzer = Mock()
    analyzer.analyze.side_effect = AssertionError("Mistral must not run for cached email")

    indexer = StubIndexer()
    result = GmailSyncService(
        CachedFetcher(), analyzer, EmailPersistenceService(db_session), indexer
    ).sync(GmailSyncRequest(limit=5, unread_only=False))

    assert result.emails[0].source == "cached"
    analyzer.analyze.assert_not_called()
    assert indexer.indexed_ids
