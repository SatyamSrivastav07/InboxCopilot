from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.user import UserRecord


class GmailConnectionRecord(Base):
    """Encrypted per-user Gmail OAuth credentials; never store raw tokens here."""

    __tablename__ = "gmail_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    google_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    granted_scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    refresh_token_available: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="connected", index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserRecord] = relationship(back_populates="gmail_connection")
