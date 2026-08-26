from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.email import EmailRecord


class MeetingRecord(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), unique=True, index=True
    )
    title: Mapped[str] = mapped_column(Text)
    raw_date: Mapped[str | None] = mapped_column(Text)
    normalized_date: Mapped[date | None] = mapped_column(Date, index=True)
    meeting_time: Mapped[time | None] = mapped_column("time", Time)
    participants: Mapped[list[str]] = mapped_column(JSON, default=list)
    location_or_link: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    email: Mapped[EmailRecord] = relationship(back_populates="meeting")

