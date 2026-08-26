from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.gmail_connection import GmailConnectionRecord


class GmailConnectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: int) -> GmailConnectionRecord | None:
        return self.db.scalar(
            select(GmailConnectionRecord).where(GmailConnectionRecord.user_id == user_id)
        )

    def add(self, connection: GmailConnectionRecord) -> GmailConnectionRecord:
        self.db.add(connection)
        return connection

    def delete_for_user(self, user_id: int) -> bool:
        connection = self.get_for_user(user_id)
        if connection is None:
            return False
        self.db.delete(connection)
        return True
