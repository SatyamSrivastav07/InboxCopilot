from __future__ import annotations

import json

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.config import Settings
from app.database.errors import RecordNotFoundError
from app.database.repositories.gmail_connection_repository import GmailConnectionRepository
from app.gmail.auth import GMAIL_SCOPES
from app.gmail.errors import GmailNotConnectedError
from app.security.token_cipher import OAuthTokenCipher
from app.services.gmail_connection_service import GmailConnectionService


class UserGmailAuthService:
    """Loads and refreshes one user's encrypted Gmail OAuth credentials."""

    def __init__(self, db, user_id: int, settings: Settings) -> None:
        self.user_id = user_id
        self.connections = GmailConnectionRepository(db)
        self.connection_service = GmailConnectionService(
            db, OAuthTokenCipher.from_settings(settings)
        )

    def is_connected(self) -> bool:
        try:
            self.get_credentials()
        except GmailNotConnectedError:
            return False
        return True

    def get_credentials(self) -> Credentials:
        try:
            saved = self.connection_service.load_credentials(self.user_id)
        except RecordNotFoundError as exc:
            raise GmailNotConnectedError("Gmail is not connected for this account.") from exc
        try:
            credentials = Credentials.from_authorized_user_info(saved, scopes=GMAIL_SCOPES)
        except (TypeError, ValueError) as exc:
            raise GmailNotConnectedError("The saved Gmail connection is invalid. Connect Gmail again.") from exc
        if credentials.expired:
            if not credentials.refresh_token:
                raise GmailNotConnectedError("The Gmail session expired. Connect Gmail again.")
            try:
                credentials.refresh(Request())
                self._save_refreshed_credentials(credentials)
            except (RefreshError, TransportError) as exc:
                raise GmailNotConnectedError("The Gmail session could not be refreshed. Connect Gmail again.") from exc
        if not credentials.valid or not set(GMAIL_SCOPES).issubset(set(credentials.scopes or [])):
            raise GmailNotConnectedError("The Gmail connection is missing required permissions. Connect Gmail again.")
        return credentials

    def _save_refreshed_credentials(self, credentials: Credentials) -> None:
        connection = self.connections.get_for_user(self.user_id)
        self.connection_service.save_credentials(
            self.user_id,
            json.loads(credentials.to_json()),
            google_email=connection.google_email if connection else None,
        )
