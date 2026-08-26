from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models.meeting import MeetingRecord


class MeetingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> list[MeetingRecord]:
        query = select(MeetingRecord).options(selectinload(MeetingRecord.email))
        if date_from is not None:
            query = query.where(MeetingRecord.normalized_date >= date_from)
        if date_to is not None:
            query = query.where(MeetingRecord.normalized_date <= date_to)
        query = query.order_by(
            MeetingRecord.normalized_date.asc().nullslast(), MeetingRecord.id.desc()
        )
        if limit is not None:
            query = query.limit(limit)
        return list(self.db.scalars(query))

    def count_upcoming(self, today: date) -> int:
        return self.db.scalar(
            select(func.count(MeetingRecord.id)).where(
                MeetingRecord.normalized_date >= today
            )
        ) or 0
