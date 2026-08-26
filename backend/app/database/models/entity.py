from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.email import EmailRecord


class EntityRecord(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_value: Mapped[str] = mapped_column(Text)

    email: Mapped[EmailRecord] = relationship(back_populates="entities")

