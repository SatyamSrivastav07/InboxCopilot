from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError, RecordNotFoundError
from app.database.models.gmail_connection import GmailConnectionRecord
from app.database.repositories.gmail_connection_repository import GmailConnectionRepository
from app.security.token_cipher import OAuthTokenCipher


class GmailConnectionService:
    """Persistence-only connection service; browser login is introduced in Phase 10."""

    def __init__(self, db: Session, cipher: OAuthTokenCipher) -> None:
        self.db = db
        self.connections = GmailConnectionRepository(db)
        self.cipher = cipher

    def save_credentials(
        self,
        user_id: int,
        credentials: dict[str, object],
        *,
        google_email: str | None = None,
    ) -> GmailConnectionRecord:
        serialized = json.dumps(credentials, separators=(",", ":"), sort_keys=True)
        connection = self.connections.get_for_user(user_id)
        if connection is None:
            connection = GmailConnectionRecord(
                user_id=user_id,
                encrypted_credentials=self.cipher.encrypt(serialized),
                google_email=google_email,
                granted_scopes=list(credentials.get("scopes") or []),
                refresh_token_available=bool(credentials.get("refresh_token")),
                status="connected",
            )
            self.connections.add(connection)
        else:
            connection.encrypted_credentials = self.cipher.encrypt(serialized)
            connection.google_email = google_email or connection.google_email
            connection.granted_scopes = list(credentials.get("scopes") or [])
            connection.refresh_token_available = bool(credentials.get("refresh_token"))
            connection.status = "connected"
            connection.disconnected_at = None
        try:
            self.db.commit()
            self.db.refresh(connection)
            return connection
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DatabaseUnavailableError("The Gmail connection could not be saved.") from exc

    def load_credentials(self, user_id: int) -> dict[str, object]:
        connection = self.connections.get_for_user(user_id)
        if connection is None or connection.status != "connected":
            raise RecordNotFoundError("Gmail connection was not found.")
        return json.loads(self.cipher.decrypt(connection.encrypted_credentials))

    def disconnect(self, user_id: int) -> None:
        connection = self.connections.get_for_user(user_id)
        if connection is None:
            return
        connection.status = "disconnected"
        connection.encrypted_credentials = self.cipher.encrypt("{}")
        connection.disconnected_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DatabaseUnavailableError("The Gmail connection could not be removed.") from exc
