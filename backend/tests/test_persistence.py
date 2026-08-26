from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.database.dependencies import get_db
from app.database.errors import PersistenceError
from app.database.models.email import EmailRecord
from app.database.models.task import TaskRecord
from app.gmail.schemas import GmailEmail
from app.main import app
from app.schemas.email import EmailAnalysis
from app.services.email_persistence import EmailPersistenceService


def gmail_email(message_id="gmail-1"):
    return GmailEmail(
        message_id=message_id,
        thread_id="thread-1",
        sender="Manager <manager@example.com>",
        recipients=["User <user@example.com>"],
        subject="Project review",
        body="Please send the report and slides by 2026-09-01.",
        received_at=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX", "UNREAD"],
    )


def analysis(category="action_required", priority="high"):
    return EmailAnalysis(
        sender="Manager <manager@example.com>",
        subject="Project review",
        summary="The manager requests the report and slides.",
        classification={
            "category": category,
            "priority": priority,
            "reason": "Two deliverables are requested by a deadline.",
        },
        tasks=[
            {
                "title": "Send report",
                "description": "Send the project report.",
                "raw_deadline": "2026-09-01",
                "normalized_deadline": "2026-09-01",
            },
            {
                "title": "Send slides",
                "description": "Send the presentation slides.",
                "raw_deadline": "2026-09-01",
                "normalized_deadline": "2026-09-01",
            },
        ],
        meeting={
            "title": "Project review",
            "date": "2026-09-02",
            "time": "14:30",
            "participants": ["Manager"],
            "location_or_link": "Conference room",
        },
        entities={
            "people": ["Manager"],
            "organizations": ["Example Corp"],
            "dates": ["2026-09-01", "2026-09-02"],
            "locations": ["Conference room"],
        },
        reply_required=True,
    )


def save(db_session, message_id="gmail-1", category="action_required", priority="high"):
    return EmailPersistenceService(db_session).save_analyzed_email(
        gmail_email(message_id), analysis(category, priority)
    )


def test_saves_analyzed_email_and_all_relationships(db_session):
    result = save(db_session)
    assert result.created is True
    assert result.email.id is not None
    assert len(result.email.tasks) == 2
    assert result.email.meeting.title == "Project review"
    assert len(result.email.entities) == 5


def test_saves_multiple_tasks_with_inherited_priority(db_session):
    record = save(db_session).email
    assert [task.title for task in record.tasks] == ["Send report", "Send slides"]
    assert all(task.priority == "high" for task in record.tasks)


def test_duplicate_gmail_message_id_returns_existing_record(db_session):
    first = save(db_session)
    second = save(db_session)
    assert first.created is True
    assert second.created is False
    assert second.email.id == first.email.id
    assert db_session.scalar(select(func.count(EmailRecord.id))) == 1
    assert db_session.scalar(select(func.count(TaskRecord.id))) == 2


def test_fetches_persisted_emails_and_filters_category(db_session, override_db):
    save(db_session, "gmail-action", "action_required", "high")
    save(db_session, "gmail-news", "newsletter", "low")
    app.dependency_overrides[get_db] = override_db
    try:
        all_response = TestClient(app).get("/api/emails")
        filtered_response = TestClient(app).get("/api/emails?category=newsletter")
    finally:
        app.dependency_overrides.clear()

    assert all_response.status_code == 200
    assert len(all_response.json()) == 2
    assert filtered_response.status_code == 200
    assert [item["classification"]["category"] for item in filtered_response.json()] == [
        "newsletter"
    ]


def test_marks_task_completed(db_session, override_db):
    task_id = save(db_session).email.tasks[0].id
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).patch(
            f"/api/tasks/{task_id}", json={"completed": True}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert db_session.get(TaskRecord, task_id).completed is True


def test_transaction_rolls_back_on_commit_failure(db_session, monkeypatch):
    real_rollback = db_session.rollback
    rollback_spy = Mock(side_effect=real_rollback)
    monkeypatch.setattr(db_session, "rollback", rollback_spy)
    monkeypatch.setattr(db_session, "commit", Mock(side_effect=SQLAlchemyError("failure")))

    with pytest.raises(PersistenceError):
        save(db_session)

    rollback_spy.assert_called_once()
    assert not db_session.new
