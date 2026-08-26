from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models.email import EmailRecord


class EmailRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _with_analysis(query: Select[tuple[EmailRecord]]) -> Select[tuple[EmailRecord]]:
        return query.options(
            selectinload(EmailRecord.tasks),
            selectinload(EmailRecord.meeting),
            selectinload(EmailRecord.entities),
        )

    def get_by_id(self, email_id: int) -> EmailRecord | None:
        query = self._with_analysis(select(EmailRecord).where(EmailRecord.id == email_id))
        return self.db.scalar(query)

    def get_by_gmail_message_id(self, gmail_message_id: str) -> EmailRecord | None:
        query = self._with_analysis(
            select(EmailRecord).where(EmailRecord.gmail_message_id == gmail_message_id)
        )
        return self.db.scalar(query)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        category: str | None = None,
        priority: str | None = None,
        reply_required: bool | None = None,
    ) -> list[EmailRecord]:
        query = select(EmailRecord)
        if category is not None:
            query = query.where(EmailRecord.category == category)
        if priority is not None:
            query = query.where(EmailRecord.priority == priority)
        if reply_required is not None:
            query = query.where(EmailRecord.reply_required.is_(reply_required))
        query = self._with_analysis(
            query.order_by(EmailRecord.received_at.desc().nullslast(), EmailRecord.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(query).unique())

    def add(self, record: EmailRecord) -> EmailRecord:
        self.db.add(record)
        return record

    def count(self) -> int:
        return self.db.scalar(select(func.count(EmailRecord.id))) or 0

    def list_all_for_indexing(self) -> list[EmailRecord]:
        return list(self.db.scalars(select(EmailRecord).order_by(EmailRecord.id)))


    def count_needs_reply(self) -> int:
        return self.db.scalar(
            select(func.count(EmailRecord.id)).where(EmailRecord.reply_required.is_(True))
        ) or 0

    def count_high_priority(self) -> int:
        return self.db.scalar(
            select(func.count(EmailRecord.id)).where(
                EmailRecord.priority.in_(["high", "urgent"])
            )
        ) or 0
