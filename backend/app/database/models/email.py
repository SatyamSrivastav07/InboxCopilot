from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.entity import EntityRecord
    from app.database.models.meeting import MeetingRecord
    from app.database.models.task import TaskRecord


class EmailRecord(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(255), index=True)
    sender: Mapped[str] = mapped_column(Text)
    recipients: Mapped[list[str]] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(Text)
    body_original: Mapped[str] = mapped_column(Text)
    body_cleaned: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)

    category: Mapped[str] = mapped_column(String(50), index=True)
    priority: Mapped[str] = mapped_column(String(20), index=True)
    classification_reason: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    reply_required: Mapped[bool] = mapped_column(Boolean, index=True)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[list[TaskRecord]] = relationship(
        back_populates="email", cascade="all, delete-orphan", passive_deletes=True
    )
    meeting: Mapped[MeetingRecord | None] = relationship(
        back_populates="email",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    entities: Mapped[list[EntityRecord]] = relationship(
        back_populates="email", cascade="all, delete-orphan", passive_deletes=True
    )

