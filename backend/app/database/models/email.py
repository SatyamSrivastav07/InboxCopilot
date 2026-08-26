from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.draft import EmailDraftRecord
    from app.database.models.entity import EntityRecord
    from app.database.models.meeting import MeetingRecord
    from app.database.models.task import TaskRecord
    from app.database.models.user import UserRecord


class EmailRecord(Base):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("user_id", "gmail_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), index=True)
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

    processing_status: Mapped[str] = mapped_column(
        String(20), default="processed", server_default="processed", index=True
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_attempts: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    vector_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", index=True
    )

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
    drafts: Mapped[list[EmailDraftRecord]] = relationship(
        back_populates="email", cascade="all, delete-orphan", passive_deletes=True
    )
    user: Mapped[UserRecord] = relationship(back_populates="emails")
