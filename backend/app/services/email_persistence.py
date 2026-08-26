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
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.emails = EmailRepository(db, user_id)
        self.user_id = self.emails.user_id

    def get_by_gmail_message_id(self, message_id: str) -> EmailRecord | None:
        try:
            return self.emails.get_by_gmail_message_id(message_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable or migrations have not been applied."
            ) from exc

    def get_by_id(self, email_id: int) -> EmailRecord | None:
        try:
            return self.emails.get_by_id(email_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable or migrations have not been applied."
            ) from exc

    def create_pending_email(self, gmail_email: GmailEmail) -> PersistenceResult:
        existing = self.get_by_gmail_message_id(gmail_email.message_id)
        if existing:
            return PersistenceResult(email=existing, created=False)
        record = EmailRecord(
            user_id=self.user_id,
            gmail_message_id=gmail_email.message_id,
            gmail_thread_id=gmail_email.thread_id,
            sender=gmail_email.sender,
            recipients=gmail_email.recipients,
            subject=gmail_email.subject,
            body_original=gmail_email.body,
            body_cleaned=gmail_email.body,
            received_at=_received_at(gmail_email.received_at),
            labels=gmail_email.labels,
            category="other",
            priority="low",
            classification_reason="Analysis is pending.",
            summary="Analysis is pending.",
            reply_required=False,
            processing_status="pending",
            processing_attempts=0,
            vector_status="pending",
        )
        try:
            self.emails.add(record)
            self.db.commit()
            self.db.refresh(record)
            return PersistenceResult(email=record, created=True)
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_gmail_message_id(gmail_email.message_id)
            if existing:
                return PersistenceResult(email=existing, created=False)
            raise PersistenceError("The Gmail email could not be reserved for processing.")
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise PersistenceError("The Gmail email could not be saved for processing.") from exc

    def complete_analysis(
        self, record: EmailRecord, analysis: EmailAnalysis
    ) -> EmailRecord:
        record.category = analysis.classification.category.value
        record.priority = analysis.classification.priority.value
        record.classification_reason = analysis.classification.reason
        record.summary = analysis.summary
        record.reply_required = analysis.reply_required
        record.processing_status = "processed"
        record.processing_error = None
        record.processing_attempts = (record.processing_attempts or 0) + 1
        record.vector_status = "pending"
        record.tasks.clear()
        record.entities.clear()
        record.meeting = None
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
        self._commit_record(record, "The analyzed email transaction was rolled back.")
        return record

    def mark_processing_failed(self, record: EmailRecord, message: str) -> None:
        record.processing_status = "failed"
        record.processing_error = message[:500]
        record.processing_attempts = (record.processing_attempts or 0) + 1
        self._commit_record(record, "The email failure state could not be saved.")

    def mark_vector_status(self, record: EmailRecord, status: str) -> None:
        record.vector_status = status
        self._commit_record(record, "The vector indexing state could not be saved.")

    def mark_reprocessing(self, record: EmailRecord) -> None:
        record.processing_status = "pending"
        record.processing_error = None
        record.vector_status = "pending"
        self._commit_record(record, "The email could not be queued for reprocessing.")

    def _commit_record(self, record: EmailRecord, message: str) -> None:
        try:
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise PersistenceError(message) from exc

    def save_analyzed_email(
        self, gmail_email: GmailEmail, analysis: EmailAnalysis
    ) -> PersistenceResult:
        existing = self.get_by_gmail_message_id(gmail_email.message_id)
        if existing and existing.processing_status == "processed":
            return PersistenceResult(email=existing, created=False)

        if existing:
            return PersistenceResult(
                email=self.complete_analysis(existing, analysis), created=False
            )

        record = EmailRecord(
            user_id=self.user_id,
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
            processing_status="processed",
            processing_attempts=1,
            vector_status="pending",
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
