from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models.email import EmailRecord
from app.database.models.task import TaskRecord
from app.database.repositories.user_scope import resolve_user_id


class TaskRepository:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = resolve_user_id(db, user_id)

    def get_by_id(self, task_id: int) -> TaskRecord | None:
        return self.db.scalar(
            select(TaskRecord)
            .join(TaskRecord.email)
            .options(selectinload(TaskRecord.email))
            .where(TaskRecord.id == task_id, EmailRecord.user_id == self.user_id)
        )

    def list(
        self,
        *,
        completed: bool | None = None,
        priority: str | None = None,
        deadline_from: date | None = None,
        deadline_to: date | None = None,
        limit: int | None = None,
    ) -> list[TaskRecord]:
        query = (
            select(TaskRecord)
            .join(TaskRecord.email)
            .options(selectinload(TaskRecord.email))
            .where(EmailRecord.user_id == self.user_id)
        )
        if completed is not None:
            query = query.where(TaskRecord.completed.is_(completed))
        if priority is not None:
            query = query.where(TaskRecord.priority == priority)
        if deadline_from is not None:
            query = query.where(TaskRecord.normalized_deadline >= deadline_from)
        if deadline_to is not None:
            query = query.where(TaskRecord.normalized_deadline <= deadline_to)
        query = query.order_by(
            TaskRecord.completed,
            TaskRecord.normalized_deadline.asc().nullslast(),
            TaskRecord.id.desc(),
        )
        if limit is not None:
            query = query.limit(limit)
        return list(self.db.scalars(query))

    def count(
        self,
        *,
        completed: bool | None = None,
        priority: str | None = None,
        deadline_from: date | None = None,
        deadline_to: date | None = None,
    ) -> int:
        query = (
            select(func.count(TaskRecord.id))
            .join(TaskRecord.email)
            .where(EmailRecord.user_id == self.user_id)
        )
        if completed is not None:
            query = query.where(TaskRecord.completed.is_(completed))
        if priority is not None:
            query = query.where(TaskRecord.priority == priority)
        if deadline_from is not None:
            query = query.where(TaskRecord.normalized_deadline >= deadline_from)
        if deadline_to is not None:
            query = query.where(TaskRecord.normalized_deadline <= deadline_to)
        return self.db.scalar(query) or 0

    def count_pending(self) -> int:
        return self.db.scalar(
            select(func.count(TaskRecord.id))
            .join(TaskRecord.email)
            .where(EmailRecord.user_id == self.user_id, TaskRecord.completed.is_(False))
        ) or 0

    def upcoming_deadlines(self, from_date: date, limit: int = 5) -> list[TaskRecord]:
        query = (
            select(TaskRecord)
            .join(TaskRecord.email)
            .options(selectinload(TaskRecord.email))
            .where(
                EmailRecord.user_id == self.user_id,
                TaskRecord.completed.is_(False),
                TaskRecord.normalized_deadline.is_not(None),
                TaskRecord.normalized_deadline >= from_date,
            )
            .order_by(TaskRecord.normalized_deadline.asc(), TaskRecord.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(query).unique())
