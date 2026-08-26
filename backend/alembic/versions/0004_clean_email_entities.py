"""Clean escaped whitespace entities from persisted email bodies.

Revision ID: 0004_clean_email_entities
Revises: 0003_processing_reliability
"""
from collections.abc import Sequence
from html import unescape
import re

from alembic import op
import sqlalchemy as sa

revision: str = "0004_clean_email_entities"
down_revision: str | None = "0003_processing_reliability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sanitize(value: str) -> str:
    for _ in range(3):
        decoded = unescape(value)
        if decoded == value:
            break
        value = decoded
    value = (
        value.replace("\u00a0", " ")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\ufeff", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def upgrade() -> None:
    connection = op.get_bind()
    emails = sa.table(
        "emails",
        sa.column("id", sa.Integer()),
        sa.column("body_original", sa.Text()),
        sa.column("body_cleaned", sa.Text()),
        sa.column("vector_status", sa.String()),
    )
    rows = connection.execute(
        sa.select(emails.c.id, emails.c.body_original, emails.c.body_cleaned)
    )
    for row in rows:
        original = _sanitize(row.body_original or "")
        cleaned = _sanitize(row.body_cleaned or "")
        if original != row.body_original or cleaned != row.body_cleaned:
            connection.execute(
                emails.update()
                .where(emails.c.id == row.id)
                .values(
                    body_original=original,
                    body_cleaned=cleaned,
                    vector_status="pending",
                )
            )


def downgrade() -> None:
    # Entity decoding is intentionally irreversible; restoring broken display
    # artifacts would not recover meaningful source content.
    pass
