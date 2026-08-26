from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError
from app.database.repositories.email_repository import EmailRepository
from app.database.repositories.meeting_repository import MeetingRepository
from app.database.repositories.task_repository import TaskRepository
from app.schemas.query import (
    StructuredIntent,
    StructuredItem,
    StructuredQuery,
    StructuredQueryResult,
)


class StructuredQueryService:
    """Executes a fixed allow-list of repository operations; it never accepts SQL."""

    def __init__(self, db: Session) -> None:
        self.emails = EmailRepository(db)
        self.tasks = TaskRepository(db)
        self.meetings = MeetingRepository(db)
        self._handlers: dict[
            StructuredIntent, Callable[[StructuredQuery], StructuredQueryResult]
        ] = {
            StructuredIntent.LIST_TASKS: self._list_tasks,
            StructuredIntent.COUNT_TASKS: self._count_tasks,
            StructuredIntent.LIST_DEADLINES: self._list_deadlines,
            StructuredIntent.LIST_MEETINGS: self._list_meetings,
            StructuredIntent.COUNT_EMAILS: self._count_emails,
            StructuredIntent.LIST_EMAILS: self._list_emails,
            StructuredIntent.NEEDS_REPLY: self._needs_reply,
            StructuredIntent.PRIORITY_SUMMARY: self._priority_summary,
        }

    def execute(self, query: StructuredQuery) -> StructuredQueryResult:
        try:
            return self._handlers[query.intent](query)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError(
                "The database is unavailable or migrations have not been applied."
            ) from exc

    @staticmethod
    def _task_item(task) -> StructuredItem:
        return StructuredItem(
            kind="task",
            title=task.title,
            description=task.description,
            date=task.normalized_deadline,
            priority=task.priority,
            completed=task.completed,
            email_id=task.email_id,
            subject=task.email.subject if task.email else None,
            sender=task.email.sender if task.email else None,
        )

    @staticmethod
    def _meeting_item(meeting) -> StructuredItem:
        return StructuredItem(
            kind="meeting",
            title=meeting.title,
            date=meeting.normalized_date,
            time=meeting.meeting_time.isoformat(timespec="minutes")
            if meeting.meeting_time
            else None,
            email_id=meeting.email_id,
            subject=meeting.email.subject if meeting.email else None,
            sender=meeting.email.sender if meeting.email else None,
        )

    @staticmethod
    def _email_item(email) -> StructuredItem:
        return StructuredItem(
            kind="email",
            title=email.subject,
            description=email.summary,
            date=email.received_at.date() if email.received_at else None,
            priority=email.priority,
            email_id=email.id,
            subject=email.subject,
            sender=email.sender,
        )

    def _task_filters(self, query: StructuredQuery) -> dict:
        return {
            "completed": query.completed,
            "priority": query.priority.value if query.priority else None,
            "deadline_from": query.date_from,
            "deadline_to": query.date_to,
        }

    def _list_tasks(self, query: StructuredQuery) -> StructuredQueryResult:
        tasks = self.tasks.list(**self._task_filters(query), limit=query.limit)
        return StructuredQueryResult(
            intent=query.intent,
            count=len(tasks),
            items=[self._task_item(item) for item in tasks],
        )

    def _count_tasks(self, query: StructuredQuery) -> StructuredQueryResult:
        return StructuredQueryResult(
            intent=query.intent,
            count=self.tasks.count(**self._task_filters(query)),
        )

    def _list_deadlines(self, query: StructuredQuery) -> StructuredQueryResult:
        filters = self._task_filters(query)
        if filters["completed"] is None:
            filters["completed"] = False
        tasks = self.tasks.list(**filters, limit=query.limit)
        return StructuredQueryResult(
            intent=query.intent,
            count=len(tasks),
            items=[self._task_item(item) for item in tasks],
        )

    def _list_meetings(self, query: StructuredQuery) -> StructuredQueryResult:
        meetings = self.meetings.list(
            date_from=query.date_from,
            date_to=query.date_to,
            limit=query.limit,
        )
        return StructuredQueryResult(
            intent=query.intent,
            count=len(meetings),
            items=[self._meeting_item(item) for item in meetings],
        )

    def _email_filters(self, query: StructuredQuery) -> dict:
        return {
            "category": query.category.value if query.category else None,
            "priority": query.priority.value if query.priority else None,
            "reply_required": query.reply_required,
            "received_from": query.date_from,
            "received_to": query.date_to,
        }

    def _count_emails(self, query: StructuredQuery) -> StructuredQueryResult:
        return StructuredQueryResult(
            intent=query.intent,
            count=self.emails.count_filtered(**self._email_filters(query)),
        )

    def _list_emails(self, query: StructuredQuery) -> StructuredQueryResult:
        emails = self.emails.list(
            **self._email_filters(query), limit=query.limit, offset=0
        )
        return StructuredQueryResult(
            intent=query.intent,
            count=len(emails),
            items=[self._email_item(item) for item in emails],
        )

    def _needs_reply(self, query: StructuredQuery) -> StructuredQueryResult:
        filters = self._email_filters(query)
        filters["reply_required"] = True
        emails = self.emails.list(
            **filters, limit=query.limit, offset=0
        )
        return StructuredQueryResult(
            intent=query.intent,
            count=self.emails.count_filtered(**filters),
            items=[self._email_item(item) for item in emails],
        )

    def _priority_summary(self, query: StructuredQuery) -> StructuredQueryResult:
        counts = self.emails.priority_counts()
        task_records = self.tasks.list(
            completed=False, priority="urgent", limit=query.limit
        ) + self.tasks.list(completed=False, priority="high", limit=query.limit)
        email_records = self.emails.list(
            limit=query.limit,
            offset=0,
            priority="urgent",
            reply_required=None,
            received_from=query.date_from,
            received_to=query.date_to,
        ) + self.emails.list(
            limit=query.limit,
            offset=0,
            priority="high",
            reply_required=True,
            received_from=query.date_from,
            received_to=query.date_to,
        )
        items = [self._task_item(item) for item in task_records]
        items.extend(self._email_item(item) for item in email_records)
        return StructuredQueryResult(
            intent=query.intent,
            count=sum(counts.values()),
            items=items[: query.limit],
            priority_counts=counts,
        )
