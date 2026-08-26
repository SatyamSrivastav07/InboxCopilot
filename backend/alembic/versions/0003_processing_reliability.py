"""Add processing and vector indexing reliability state.

Revision ID: 0003_processing_reliability
Revises: 0002_email_drafts
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_processing_reliability"
down_revision: str | None = "0002_email_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "emails",
        sa.Column("processing_status", sa.String(length=20), server_default="processed", nullable=False),
    )
    op.add_column("emails", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column(
        "emails",
        sa.Column("processing_attempts", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "emails",
        sa.Column("vector_status", sa.String(length=20), server_default="pending", nullable=False),
    )
    op.create_index(op.f("ix_emails_processing_status"), "emails", ["processing_status"])
    op.create_index(op.f("ix_emails_vector_status"), "emails", ["vector_status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_emails_vector_status"), table_name="emails")
    op.drop_index(op.f("ix_emails_processing_status"), table_name="emails")
    op.drop_column("emails", "vector_status")
    op.drop_column("emails", "processing_attempts")
    op.drop_column("emails", "processing_error")
    op.drop_column("emails", "processing_status")
