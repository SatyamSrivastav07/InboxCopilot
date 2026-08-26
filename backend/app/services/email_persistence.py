from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError, PersistenceError
from app.database.models.email import EmailRecord
from app.database.models.entity import EntityRecord
from app.database.models.meeting import MeetingRecord
from app.database.models.task import TaskRecord
from app.database.repositories.email_repository import EmailRepository
from app.gmail.schemas import GmailEmail
from app.schemas.email import EmailAnalysis


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _clock_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _received_at(value: datetime | str) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class PersistenceResult:
    email: EmailRecord
    created: bool


class EmailPersistenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.emails = EmailRepository(db)

    def get_by_gmail_message_id(self, message_id: str) -> EmailRecord | None:
        try:
            return self.emails.get_by_gmail_message_id(message_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable or migrations have not been applied."
            ) from exc

    def save_analyzed_email(
        self, gmail_email: GmailEmail, analysis: EmailAnalysis
    ) -> PersistenceResult:
        existing = self.get_by_gmail_message_id(gmail_email.message_id)
        if existing:
            return PersistenceResult(email=existing, created=False)

        record = EmailRecord(
            gmail_message_id=gmail_email.message_id,
            gmail_thread_id=gmail_email.thread_id,
            sender=gmail_email.sender,
            recipients=gmail_email.recipients,
            subject=gmail_email.subject,
            body_original=gmail_email.body,
            body_cleaned=gmail_email.body,
            received_at=_received_at(gmail_email.received_at),
            labels=gmail_email.labels,
            category=analysis.classification.category.value,
            priority=analysis.classification.priority.value,
            classification_reason=analysis.classification.reason,
            summary=analysis.summary,
            reply_required=analysis.reply_required,
        )
        record.tasks = [
            TaskRecord(
                title=task.title,
                description=task.description,
                raw_deadline=task.raw_deadline,
                normalized_deadline=_iso_date(task.normalized_deadline),
                priority=analysis.classification.priority.value,
                completed=False,
            )
            for task in analysis.tasks
        ]
        if analysis.meeting:
            record.meeting = MeetingRecord(
                title=analysis.meeting.title,
                raw_date=analysis.meeting.date,
                normalized_date=_iso_date(analysis.meeting.date),
                meeting_time=_clock_time(analysis.meeting.time),
                participants=analysis.meeting.participants,
                location_or_link=analysis.meeting.location_or_link,
            )

        entity_groups = {
            "person": analysis.entities.people,
            "organization": analysis.entities.organizations,
            "date": analysis.entities.dates,
            "location": analysis.entities.locations,
        }
        record.entities = [
            EntityRecord(entity_type=entity_type, entity_value=value)
            for entity_type, values in entity_groups.items()
            for value in dict.fromkeys(values)
        ]

        try:
            self.emails.add(record)
            self.db.commit()
            return PersistenceResult(email=record, created=True)
        except IntegrityError:
            # The unique constraint is the final guard against concurrent syncs.
            self.db.rollback()
            existing = self.get_by_gmail_message_id(gmail_email.message_id)
            if existing:
                return PersistenceResult(email=existing, created=False)
            raise PersistenceError("The analyzed email could not be saved.")
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise PersistenceError("The analyzed email transaction was rolled back.") from exc

