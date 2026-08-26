from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models.task import TaskRecord


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, task_id: int) -> TaskRecord | None:
        return self.db.scalar(
            select(TaskRecord)
            .options(selectinload(TaskRecord.email))
            .where(TaskRecord.id == task_id)
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
        query = select(TaskRecord).options(selectinload(TaskRecord.email))
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
        query = select(func.count(TaskRecord.id))
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
            select(func.count(TaskRecord.id)).where(TaskRecord.completed.is_(False))
        ) or 0
