"""Create email drafts for the human-approved reply lifecycle.

Revision ID: 0002_email_drafts
Revises: 0001_initial
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_email_drafts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=False),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(length=20), nullable=False),
        sa.Column("generated_body", sa.Text(), nullable=False),
        sa.Column("edited_body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("in_reply_to", sa.Text(), nullable=True),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("validation_notes", sa.JSON(), nullable=False),
        sa.Column("attachment_warning", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("sent_gmail_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], name=op.f("fk_email_drafts_email_id_emails"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_drafts")),
    )
    op.create_index(op.f("ix_email_drafts_email_id"), "email_drafts", ["email_id"])
    op.create_index(op.f("ix_email_drafts_gmail_message_id"), "email_drafts", ["gmail_message_id"])
    op.create_index(op.f("ix_email_drafts_gmail_thread_id"), "email_drafts", ["gmail_thread_id"])
    op.create_index(op.f("ix_email_drafts_status"), "email_drafts", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_email_drafts_status"), table_name="email_drafts")
    op.drop_index(op.f("ix_email_drafts_gmail_thread_id"), table_name="email_drafts")
    op.drop_index(op.f("ix_email_drafts_gmail_message_id"), table_name="email_drafts")
    op.drop_index(op.f("ix_email_drafts_email_id"), table_name="email_drafts")
    op.drop_table("email_drafts")
