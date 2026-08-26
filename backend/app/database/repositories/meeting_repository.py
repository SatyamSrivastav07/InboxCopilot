from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models.email import EmailRecord
from app.database.models.meeting import MeetingRecord
from app.database.repositories.user_scope import resolve_user_id


class MeetingRepository:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = resolve_user_id(db, user_id)

    def list(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> list[MeetingRecord]:
        query = (
            select(MeetingRecord)
            .join(MeetingRecord.email)
            .options(selectinload(MeetingRecord.email))
            .where(EmailRecord.user_id == self.user_id)
        )
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
            select(func.count(MeetingRecord.id))
            .join(MeetingRecord.email)
            .where(
                EmailRecord.user_id == self.user_id,
                MeetingRecord.normalized_date >= today
            )
        ) or 0
