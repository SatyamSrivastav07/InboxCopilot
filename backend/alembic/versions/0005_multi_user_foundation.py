"""Add user ownership and encrypted Gmail connection persistence.

Existing single-user inbox data is assigned to one explicit legacy account. This
preserves local data while Phase 10 introduces authenticated user selection.

Revision ID: 0005_multi_user_foundation
Revises: 0004_clean_email_entities
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_multi_user_foundation"
down_revision: str | None = "0004_clean_email_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_SUBJECT = "legacy-local-user"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("google_subject", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("google_subject", name=op.f("uq_users_google_subject")),
    )
    op.create_table(
        "gmail_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("google_email", sa.String(length=320), nullable=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("granted_scopes", sa.JSON(), nullable=False),
        sa.Column("refresh_token_available", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_gmail_connections_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gmail_connections")),
        sa.UniqueConstraint("user_id", name=op.f("uq_gmail_connections_user_id")),
    )
    op.create_index(op.f("ix_gmail_connections_status"), "gmail_connections", ["status"])
    op.create_index(op.f("ix_gmail_connections_user_id"), "gmail_connections", ["user_id"])

    op.execute(
        sa.text(
            "INSERT INTO users (google_subject, email, display_name, status) "
            "VALUES (:subject, :email, :display_name, 'active')"
        ).bindparams(
            subject=LEGACY_SUBJECT,
            email="legacy@local.invalid",
            display_name="Legacy local inbox",
        )
    )

    op.add_column("emails", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE emails SET user_id = "
            "(SELECT id FROM users WHERE google_subject = :subject)"
        ).bindparams(subject=LEGACY_SUBJECT)
    )
    op.alter_column("emails", "user_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(op.f("fk_emails_user_id_users"), "emails", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index(op.f("ix_emails_user_id"), "emails", ["user_id"])
    op.drop_index(op.f("ix_emails_gmail_message_id"), table_name="emails")
    op.create_index(op.f("ix_emails_gmail_message_id"), "emails", ["gmail_message_id"])
    op.create_unique_constraint(op.f("uq_emails_user_id"), "emails", ["user_id", "gmail_message_id"])

    op.add_column("email_drafts", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE email_drafts SET user_id = emails.user_id FROM emails WHERE email_drafts.email_id = emails.id"))
    op.alter_column("email_drafts", "user_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(op.f("fk_email_drafts_user_id_users"), "email_drafts", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index(op.f("ix_email_drafts_user_id"), "email_drafts", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_email_drafts_user_id"), table_name="email_drafts")
    op.drop_constraint(op.f("fk_email_drafts_user_id_users"), "email_drafts", type_="foreignkey")
    op.drop_column("email_drafts", "user_id")
    op.drop_constraint(op.f("uq_emails_user_id"), "emails", type_="unique")
    op.drop_index(op.f("ix_emails_gmail_message_id"), table_name="emails")
    op.create_index(op.f("ix_emails_gmail_message_id"), "emails", ["gmail_message_id"], unique=True)
    op.drop_index(op.f("ix_emails_user_id"), table_name="emails")
    op.drop_constraint(op.f("fk_emails_user_id_users"), "emails", type_="foreignkey")
    op.drop_column("emails", "user_id")
    op.drop_index(op.f("ix_gmail_connections_user_id"), table_name="gmail_connections")
    op.drop_index(op.f("ix_gmail_connections_status"), table_name="gmail_connections")
    op.drop_table("gmail_connections")
    op.drop_table("users")
