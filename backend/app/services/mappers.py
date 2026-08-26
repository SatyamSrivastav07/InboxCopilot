from __future__ import annotations

from app.database.models.email import EmailRecord
from app.database.models.meeting import MeetingRecord
from app.database.models.task import TaskRecord
from app.gmail.schemas import GmailEmail
from app.schemas.email import EmailAnalysis, Entities
from app.schemas.persistence import (
    PersistedEmail,
    PersistedEntity,
    PersistedMeeting,
    PersistedTask,
    SourceEmail,
)


def source_email(record: EmailRecord) -> SourceEmail:
    return SourceEmail(id=record.id, sender=record.sender, subject=record.subject)


def task_response(record: TaskRecord, include_source: bool = False) -> PersistedTask:
    return PersistedTask(
        id=record.id,
        email_id=record.email_id,
        title=record.title,
        description=record.description,
        raw_deadline=record.raw_deadline,
        normalized_deadline=record.normalized_deadline,
        priority=record.priority,
        completed=record.completed,
        created_at=record.created_at,
        updated_at=record.updated_at,
        source_email=source_email(record.email) if include_source else None,
    )


def meeting_response(
    record: MeetingRecord, include_source: bool = False
) -> PersistedMeeting:
    return PersistedMeeting(
        id=record.id,
        email_id=record.email_id,
        title=record.title,
        raw_date=record.raw_date,
        normalized_date=record.normalized_date,
        meeting_time=record.meeting_time,
        participants=record.participants,
        location_or_link=record.location_or_link,
        created_at=record.created_at,
        updated_at=record.updated_at,
        source_email=source_email(record.email) if include_source else None,
    )


def email_response(record: EmailRecord) -> PersistedEmail:
    return PersistedEmail(
        id=record.id,
        gmail_message_id=record.gmail_message_id,
        gmail_thread_id=record.gmail_thread_id,
        sender=record.sender,
        recipients=record.recipients,
        subject=record.subject,
        body_original=record.body_original,
        body_cleaned=record.body_cleaned,
        received_at=record.received_at,
        labels=record.labels,
        summary=record.summary,
        classification={
            "category": record.category,
            "priority": record.priority,
            "reason": record.classification_reason,
        },
        reply_required=record.reply_required,
        tasks=[task_response(task) for task in record.tasks],
        meeting=meeting_response(record.meeting) if record.meeting else None,
        entities=[PersistedEntity.model_validate(entity) for entity in record.entities],
        processed_at=record.processed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def record_to_gmail(record: EmailRecord) -> GmailEmail:
    return GmailEmail(
        message_id=record.gmail_message_id,
        thread_id=record.gmail_thread_id,
        sender=record.sender,
        recipients=record.recipients,
        subject=record.subject,
        body=record.body_cleaned,
        received_at=record.received_at or "",
        labels=record.labels,
    )


def record_to_analysis(record: EmailRecord) -> EmailAnalysis:
    grouped = {"person": [], "organization": [], "date": [], "location": []}
    for entity in record.entities:
        grouped.setdefault(entity.entity_type, []).append(entity.entity_value)
    return EmailAnalysis(
        sender=record.sender,
        subject=record.subject,
        summary=record.summary,
        classification={
            "category": record.category,
            "priority": record.priority,
            "reason": record.classification_reason,
        },
        tasks=[
            {
                "title": task.title,
                "description": task.description,
                "raw_deadline": task.raw_deadline,
                "normalized_deadline": (
                    task.normalized_deadline.isoformat() if task.normalized_deadline else None
                ),
            }
            for task in record.tasks
        ],
        meeting=(
            {
                "title": record.meeting.title,
                "date": record.meeting.raw_date,
                "time": (
                    record.meeting.meeting_time.strftime("%H:%M")
                    if record.meeting.meeting_time
                    else None
                ),
                "participants": record.meeting.participants,
                "location_or_link": record.meeting.location_or_link,
            }
            if record.meeting
            else None
        ),
        entities=Entities(
            people=grouped.get("person", []),
            organizations=grouped.get("organization", []),
            dates=grouped.get("date", []),
            locations=grouped.get("location", []),
        ),
        reply_required=record.reply_required,
    )

