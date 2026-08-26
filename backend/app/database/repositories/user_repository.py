from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import UserRecord

LEGACY_LOCAL_SUBJECT = "legacy-local-user"


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> UserRecord | None:
        return self.db.get(UserRecord, user_id)

    def get_by_google_subject(self, google_subject: str) -> UserRecord | None:
        return self.db.scalar(
            select(UserRecord).where(UserRecord.google_subject == google_subject)
        )

    def get_or_create_google_user(
        self,
        *,
        google_subject: str,
        email: str,
        display_name: str | None,
        avatar_url: str | None,
    ) -> UserRecord:
        record = self.get_by_google_subject(google_subject)
        if record is None:
            record = self.db.scalar(select(UserRecord).where(UserRecord.email == email))
        if record is None:
            record = UserRecord(
                google_subject=google_subject,
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
                status="active",
            )
            self.db.add(record)
        else:
            if record.google_subject and record.google_subject != google_subject:
                raise ValueError("This email is already linked to a different Google account.")
            record.google_subject = google_subject
            record.email = email
            record.display_name = display_name or record.display_name
            record.avatar_url = avatar_url or record.avatar_url
            record.status = "active"
        self.db.flush()
        return record

    def get_or_create_legacy_user(self) -> UserRecord:
        record = self.get_by_google_subject(LEGACY_LOCAL_SUBJECT)
        if record is not None:
            return record
        record = UserRecord(
            google_subject=LEGACY_LOCAL_SUBJECT,
            email="legacy@local.invalid",
            display_name="Legacy local inbox",
            status="active",
        )
        self.db.add(record)
        self.db.flush()
        return record
