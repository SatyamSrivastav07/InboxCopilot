from __future__ import annotations

from datetime import date

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError, RecordNotFoundError
from app.database.repositories.email_repository import EmailRepository
from app.database.repositories.meeting_repository import MeetingRepository
from app.database.repositories.task_repository import TaskRepository
from app.schemas.persistence import (
    DashboardDeadline,
    DashboardEmail,
    DashboardOverview,
    DashboardStats,
    PersistedEmail,
    PersistedMeeting,
    PersistedTask,
)
from app.services.mappers import email_response, meeting_response, task_response


class InboxQueryService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.emails = EmailRepository(db, user_id)
        self.tasks = TaskRepository(db, self.emails.user_id)
        self.meetings = MeetingRepository(db, self.emails.user_id)

    def _database_error(self, exc: SQLAlchemyError) -> DatabaseUnavailableError:
        return DatabaseUnavailableError(
            "The database is unavailable or migrations have not been applied."
        )

    def list_emails(self, **filters) -> list[PersistedEmail]:
        try:
            return [email_response(item) for item in self.emails.list(**filters)]
        except SQLAlchemyError as exc:
            raise self._database_error(exc) from exc

    def get_email(self, email_id: int) -> PersistedEmail:
        try:
            item = self.emails.get_by_id(email_id)
        except SQLAlchemyError as exc:
            raise self._database_error(exc) from exc
        if item is None:
            raise RecordNotFoundError("Persisted email was not found.")
        return email_response(item)

    def list_tasks(self, **filters) -> list[PersistedTask]:
        try:
            return [
                task_response(item, include_source=True)
                for item in self.tasks.list(**filters)
            ]
        except SQLAlchemyError as exc:
            raise self._database_error(exc) from exc

    def update_task(self, task_id: int, completed: bool) -> PersistedTask:
        try:
            item = self.tasks.get_by_id(task_id)
            if item is None:
                raise RecordNotFoundError("Task was not found.")
            item.completed = completed
            self.db.commit()
            self.db.refresh(item)
            return task_response(item, include_source=True)
        except RecordNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise self._database_error(exc) from exc

    def list_meetings(self, **filters) -> list[PersistedMeeting]:
        try:
            return [
                meeting_response(item, include_source=True)
                for item in self.meetings.list(**filters)
            ]
        except SQLAlchemyError as exc:
            raise self._database_error(exc) from exc

    def dashboard(self) -> DashboardStats:
        try:
            return DashboardStats(
                total_emails=self.emails.count(),
                needs_reply=self.emails.count_needs_reply(),
                pending_tasks=self.tasks.count_pending(),
                high_urgent=self.emails.count_high_priority(),
                upcoming_meetings=self.meetings.count_upcoming(date.today()),
            )
        except SQLAlchemyError as exc:
            raise self._database_error(exc) from exc

    def dashboard_overview(self) -> DashboardOverview:
        stats = self.dashboard()
        try:
            return DashboardOverview(
                stats=stats,
                recent_important=[
                    DashboardEmail(
                        id=email.id,
                        sender=email.sender,
                        subject=email.subject,
                        summary=email.summary,
                        priority=email.priority,
                        received_at=email.received_at,
                    )
                    for email in self.emails.recent_important()
                ],
                upcoming_deadlines=[
                    DashboardDeadline(
                        id=task.id,
                        email_id=task.email_id,
                        title=task.title,
                        normalized_deadline=task.normalized_deadline,
                        priority=task.priority,
                        source_subject=task.email.subject,
                    )
                    for task in self.tasks.upcoming_deadlines(date.today())
                    if task.normalized_deadline is not None
                ],
            )
        except SQLAlchemyError as exc:
            raise self._database_error(exc) from exc
