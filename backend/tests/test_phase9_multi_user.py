from __future__ import annotations

from cryptography.fernet import Fernet

from app.cache.keys import dashboard_key, gmail_sync_lock_key, inbox_reindex_lock_key
from app.database.models.email import EmailRecord
from app.database.models.task import TaskRecord
from app.database.models.user import UserRecord
from app.database.repositories.email_repository import EmailRepository
from app.database.repositories.task_repository import TaskRepository
from app.security.token_cipher import OAuthTokenCipher
from app.services.gmail_connection_service import GmailConnectionService


def email_record(*, user_id: int, message_id: str) -> EmailRecord:
    return EmailRecord(
        user_id=user_id,
        gmail_message_id=message_id,
        gmail_thread_id=f"thread-{message_id}",
        sender="sender@example.com",
        recipients=["person@example.com"],
        subject="Private work item",
        body_original="Please finish the private work item.",
        body_cleaned="Please finish the private work item.",
        received_at=None,
        labels=["INBOX"],
        category="action_required",
        priority="high",
        classification_reason="Action is requested.",
        summary="A private work item.",
        reply_required=True,
    )


def test_repositories_scope_emails_and_tasks_to_the_selected_user(db_session):
    owner = UserRecord(google_subject="owner-subject", email="owner@example.com")
    other = UserRecord(google_subject="other-subject", email="other@example.com")
    db_session.add_all([owner, other])
    db_session.flush()
    owned_email = email_record(user_id=owner.id, message_id="same-gmail-message")
    owned_email.tasks = [
        TaskRecord(
            title="Owner task",
            description="Only the owner can see this.",
            priority="high",
            completed=False,
        )
    ]
    other_email = email_record(user_id=other.id, message_id="same-gmail-message")
    db_session.add_all([owned_email, other_email])
    db_session.commit()

    assert EmailRepository(db_session, owner.id).get_by_gmail_message_id(
        "same-gmail-message"
    ).id == owned_email.id
    assert EmailRepository(db_session, other.id).get_by_gmail_message_id(
        "same-gmail-message"
    ).id == other_email.id
    assert [task.title for task in TaskRepository(db_session, owner.id).list()] == [
        "Owner task"
    ]
    assert TaskRepository(db_session, other.id).list() == []


def test_gmail_credentials_are_encrypted_per_user(db_session):
    user = UserRecord(google_subject="oauth-subject", email="oauth@example.com")
    db_session.add(user)
    db_session.commit()
    cipher = OAuthTokenCipher(Fernet.generate_key().decode("utf-8"))
    service = GmailConnectionService(db_session, cipher)
    credentials = {
        "token": "access-token-value",
        "refresh_token": "refresh-token-value",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }

    connection = service.save_credentials(
        user.id, credentials, google_email="oauth@example.com"
    )

    assert "access-token-value" not in connection.encrypted_credentials
    assert service.load_credentials(user.id) == credentials
    service.disconnect(user.id)
    assert service.connections.get_for_user(user.id).status == "disconnected"


def test_user_scoped_cache_and_job_keys_are_distinct():
    assert dashboard_key(5) == "cache:dashboard:v3:user:5"
    assert gmail_sync_lock_key(5) == "lock:gmail-sync:user:5"
    assert inbox_reindex_lock_key(5) == "lock:inbox-reindex:user:5"
    assert gmail_sync_lock_key(5) != gmail_sync_lock_key(6)
