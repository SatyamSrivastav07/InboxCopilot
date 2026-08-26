"""Create emails, tasks, meetings, and entities.

Revision ID: 0001_initial
Revises:
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=False),
        sa.Column("sender", sa.Text(), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_original", sa.Text(), nullable=False),
        sa.Column("body_cleaned", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("classification_reason", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reply_required", sa.Boolean(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emails")),
    )
    op.create_index(op.f("ix_emails_gmail_message_id"), "emails", ["gmail_message_id"], unique=True)
    op.create_index(op.f("ix_emails_gmail_thread_id"), "emails", ["gmail_thread_id"])
    op.create_index(op.f("ix_emails_received_at"), "emails", ["received_at"])
    op.create_index(op.f("ix_emails_category"), "emails", ["category"])
    op.create_index(op.f("ix_emails_priority"), "emails", ["priority"])
    op.create_index(op.f("ix_emails_reply_required"), "emails", ["reply_required"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("raw_deadline", sa.Text(), nullable=True),
        sa.Column("normalized_deadline", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], name=op.f("fk_tasks_email_id_emails"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_email_id"), "tasks", ["email_id"])
    op.create_index(op.f("ix_tasks_normalized_deadline"), "tasks", ["normalized_deadline"])
    op.create_index(op.f("ix_tasks_completed"), "tasks", ["completed"])
    op.create_index(op.f("ix_tasks_priority"), "tasks", ["priority"])

    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("raw_date", sa.Text(), nullable=True),
        sa.Column("normalized_date", sa.Date(), nullable=True),
        sa.Column("time", sa.Time(), nullable=True),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("location_or_link", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], name=op.f("fk_meetings_email_id_emails"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_meetings")),
    )
    op.create_index(op.f("ix_meetings_email_id"), "meetings", ["email_id"], unique=True)
    op.create_index(op.f("ix_meetings_normalized_date"), "meetings", ["normalized_date"])

    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], name=op.f("fk_entities_email_id_emails"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entities")),
    )
    op.create_index(op.f("ix_entities_email_id"), "entities", ["email_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_entities_email_id"), table_name="entities")
    op.drop_table("entities")
    op.drop_index(op.f("ix_meetings_normalized_date"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_email_id"), table_name="meetings")
    op.drop_table("meetings")
    op.drop_index(op.f("ix_tasks_priority"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_completed"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_normalized_deadline"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_email_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_emails_reply_required"), table_name="emails")
    op.drop_index(op.f("ix_emails_priority"), table_name="emails")
    op.drop_index(op.f("ix_emails_category"), table_name="emails")
    op.drop_index(op.f("ix_emails_received_at"), table_name="emails")
    op.drop_index(op.f("ix_emails_gmail_thread_id"), table_name="emails")
    op.drop_index(op.f("ix_emails_gmail_message_id"), table_name="emails")
    op.drop_table("emails")

