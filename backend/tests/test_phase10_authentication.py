from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.google_oauth import GoogleOAuthService
from app.config import Settings
from app.database.dependencies import get_db
from app.database.models.gmail_connection import GmailConnectionRecord
from app.database.models.user import UserRecord
from app.database.repositories.user_repository import UserRepository
from app.main import app
from app.services.jobs import JobNotFoundError, JobService
from app.vectorstore.dependencies import get_vector_store


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


def test_local_http_google_callback_enables_only_oauthlib_development_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("OAUTHLIB_INSECURE_TRANSPORT", raising=False)

    GoogleOAuthService(oauth_settings(tmp_path)).authorization_url({})

    assert os.environ["OAUTHLIB_INSECURE_TRANSPORT"] == "1"


def test_google_oauth_rejects_a_callback_with_the_wrong_state(tmp_path):
    service = GoogleOAuthService(oauth_settings(tmp_path))
    browser_session = {}
    service.authorization_url(browser_session)

    with pytest.raises(Exception, match="state is invalid or expired"):
        service.exchange_code("unused-code", "wrong-state", browser_session)


def test_google_oauth_reports_a_safe_error_type_for_unexpected_exchange_failures(tmp_path, monkeypatch):
    service = GoogleOAuthService(oauth_settings(tmp_path))
    browser_session = {}
    authorization_url = service.authorization_url(browser_session)
    state = parse_qs(urlparse(authorization_url).query)["state"][0]

    monkeypatch.setattr(service, "_flow", lambda **_kwargs: (_ for _ in ()).throw(ValueError()))

    with pytest.raises(Exception, match="ValueError"):
        service.exchange_code("unused-code", state, browser_session)


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


class _VectorStore:
    def __init__(self):
        self.deleted_user_ids = []

    def delete_user(self, user_id):
        self.deleted_user_ids.append(user_id)


def test_account_deletion_clears_vectors_and_user_data(db_session, override_db):
    user = UserRecord(
        google_subject="delete-subject", email="delete@example.com", status="active"
    )
    db_session.add(user)
    db_session.commit()
    vector_store = _VectorStore()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_vector_store] = lambda: vector_store

    response = TestClient(app).request(
        "DELETE", "/api/auth/account", json={"confirmation": "DELETE"}
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert vector_store.deleted_user_ids == [user.id]
    assert db_session.get(UserRecord, user.id) is None


def test_gmail_disconnect_removes_saved_credentials(db_session, override_db):
    user = UserRecord(
        google_subject="disconnect-subject", email="disconnect@example.com", status="active"
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        GmailConnectionRecord(
            user_id=user.id,
            encrypted_credentials="encrypted",
            granted_scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
    )
    db_session.commit()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user

    response = TestClient(app).delete("/api/gmail/connection")

    assert response.status_code == 204
    assert db_session.get(GmailConnectionRecord, 1) is None


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
