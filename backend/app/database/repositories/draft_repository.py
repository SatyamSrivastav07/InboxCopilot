from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.draft import EmailDraftRecord
from app.database.repositories.user_scope import resolve_user_id


class DraftRepository:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = resolve_user_id(db, user_id)

    def add(self, draft: EmailDraftRecord) -> EmailDraftRecord:
        self.db.add(draft)
        return draft

    def get(self, draft_id: int) -> EmailDraftRecord | None:
        return self.db.scalar(
            select(EmailDraftRecord)
            .options(selectinload(EmailDraftRecord.email))
            .where(
                EmailDraftRecord.id == draft_id,
                EmailDraftRecord.user_id == self.user_id,
            )
        )

    def get_for_update(self, draft_id: int) -> EmailDraftRecord | None:
        return self.db.scalar(
            select(EmailDraftRecord)
            .options(selectinload(EmailDraftRecord.email))
            .where(
                EmailDraftRecord.id == draft_id,
                EmailDraftRecord.user_id == self.user_id,
            )
            .with_for_update()
        )
