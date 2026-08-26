from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.draft import EmailDraftRecord


class DraftRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, draft: EmailDraftRecord) -> EmailDraftRecord:
        self.db.add(draft)
        return draft

    def get(self, draft_id: int) -> EmailDraftRecord | None:
        return self.db.scalar(
            select(EmailDraftRecord)
            .options(selectinload(EmailDraftRecord.email))
            .where(EmailDraftRecord.id == draft_id)
        )

    def get_for_update(self, draft_id: int) -> EmailDraftRecord | None:
        return self.db.scalar(
            select(EmailDraftRecord)
            .options(selectinload(EmailDraftRecord.email))
            .where(EmailDraftRecord.id == draft_id)
            .with_for_update()
        )
