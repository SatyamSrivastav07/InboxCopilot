from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.google_oauth import GoogleOAuthService
from app.config import Settings
from app.database.dependencies import get_db
from app.database.models.user import UserRecord
from app.database.repositories.user_repository import UserRepository
from app.main import app
from app.services.jobs import JobNotFoundError, JobService


def oauth_settings(tmp_path) -> Settings:
    return Settings(
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:8000/api/gmail/callback",
        gmail_token_file=tmp_path / "token.json",
        token_encryption_key="unused-in-this-test",
    )


def test_session_status_is_public_but_inbox_routes_require_a_signed_in_user(override_db):
    app.dependency_overrides.clear()
    # The public session endpoint still receives a database dependency. Use the
    # in-memory test database so this assertion does not depend on a developer
    # .env file (or on CI having a PostgreSQL URL configured).
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    assert client.get("/api/auth/session").json() == {
        "authenticated": False,
        "user": None,
    }
    assert client.get("/api/dashboard").status_code == 401


def test_google_authorization_binds_state_and_pkce_verifier_to_browser_session(tmp_path):
    browser_session = {}
    url = GoogleOAuthService(oauth_settings(tmp_path)).authorization_url(browser_session)
    query = parse_qs(urlparse(url).query)

    assert query["state"][0] == browser_session["google_oauth_pending"]["state"]
    assert browser_session["google_oauth_pending"]["code_verifier"]
    assert "openid" in query["scope"][0].split()
    assert "email" in query["scope"][0].split()


def test_google_oauth_rejects_a_callback_with_the_wrong_state(tmp_path):
    service = GoogleOAuthService(oauth_settings(tmp_path))
    browser_session = {}
    service.authorization_url(browser_session)

    with pytest.raises(Exception, match="state is invalid or expired"):
        service.exchange_code("unused-code", "wrong-state", browser_session)


def test_google_identity_repository_reuses_the_same_subject(db_session):
    repository = UserRepository(db_session)
    first = repository.get_or_create_google_user(
        google_subject="google-subject-1",
        email="person@example.com",
        display_name="First Name",
        avatar_url=None,
    )
    db_session.commit()
    second = repository.get_or_create_google_user(
        google_subject="google-subject-1",
        email="person@example.com",
        display_name="Updated Name",
        avatar_url="https://example.com/avatar.png",
    )

    assert first.id == second.id
    assert second.display_name == "Updated Name"
    assert second.avatar_url == "https://example.com/avatar.png"


class _Redis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, _ttl, value):
        self.data[key] = str(value)

    def exists(self, key):
        return int(key in self.data)

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)


class _Celery:
    def AsyncResult(self, _job_id):
        return type("Result", (), {"state": "PENDING", "info": {}})()

    def send_task(self, *_args, **_kwargs):
        return None


def test_job_status_does_not_expose_another_users_job():
    jobs = JobService(_Celery(), _Redis())
    queued = jobs.enqueue("test.task", user_id=7)

    with pytest.raises(JobNotFoundError):
        jobs.status(queued.job_id, user_id=8)
