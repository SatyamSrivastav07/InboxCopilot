from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.email import EmailRecord


class EmailDraftRecord(Base):
    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )
    gmail_message_id: Mapped[str] = mapped_column(String(255), index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(255), index=True)
    recipient: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    instruction: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(20))
    generated_body: Mapped[str] = mapped_column(Text)
    edited_body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    in_reply_to: Mapped[str | None] = mapped_column(Text)
    references: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    attachment_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    sent_gmail_message_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    email: Mapped[EmailRecord] = relationship(back_populates="drafts")
