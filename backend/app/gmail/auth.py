from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from pathlib import Path

from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2 import OAuth2Error

from app.config import Settings
from app.gmail.errors import GmailNotConnectedError, GmailOAuthError

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
OAUTH_STATE_TTL_SECONDS = 10 * 60
logger = logging.getLogger(__name__)


class GmailAuthService:
    """Manages a single local-development Gmail OAuth connection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token_file = settings.gmail_token_file
        # PKCE requires the verifier created for the authorization request to
        # be reused during the callback token exchange.
        self._pending_states: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def _client_config(self) -> dict[str, object]:
        client_id, client_secret = self._settings.require_google_oauth()
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self._settings.google_redirect_uri],
            }
        }

    def _flow(self, state: str | None = None) -> Flow:
        flow = Flow.from_client_config(
            self._client_config(), scopes=[GMAIL_READONLY_SCOPE], state=state
        )
        flow.redirect_uri = self._settings.google_redirect_uri
        return flow

    def authorization_url(self) -> str:
        state = secrets.token_urlsafe(32)
        flow = self._flow(state=state)
        url, returned_state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        now = time.monotonic()
        with self._lock:
            self._pending_states = {
                value: pending
                for value, pending in self._pending_states.items()
                if now - pending[0] < OAUTH_STATE_TTL_SECONDS
            }
            self._pending_states[returned_state] = (now, flow.code_verifier or "")
        return url

    def exchange_code(self, code: str, state: str) -> None:
        with self._lock:
            pending = self._pending_states.pop(state, None)
        if pending is None or time.monotonic() - pending[0] >= OAUTH_STATE_TTL_SECONDS:
            raise GmailOAuthError("The OAuth state is invalid or expired. Start the connection again.")
        code_verifier = pending[1]
        if not code_verifier:
            raise GmailOAuthError("The OAuth PKCE verifier is missing. Start the connection again.")

        try:
            flow = self._flow(state=state)
            flow.code_verifier = code_verifier
            flow.fetch_token(code=code)
            self._save_credentials(flow.credentials)
        except GmailOAuthError:
            raise
        except OAuth2Error as exc:
            logger.exception("Google rejected the OAuth token exchange")
            error_code = getattr(exc, "error", None) or exc.__class__.__name__
            description = getattr(exc, "description", None) or "Token exchange was rejected."
            raise GmailOAuthError(
                f"Google OAuth failed: {error_code}. {description}"
            ) from exc
        except Exception as exc:
            logger.exception("Google OAuth token exchange failed")
            raise GmailOAuthError(
                f"Google OAuth could not be completed ({exc.__class__.__name__}). "
                "Check the backend terminal for details."
            ) from exc

    def is_connected(self) -> bool:
        try:
            self.get_credentials()
        except GmailNotConnectedError:
            return False
        return True

    def get_credentials(self) -> Credentials:
        if not self._token_file.exists():
            raise GmailNotConnectedError("Gmail is not connected.")
        try:
            credentials = Credentials.from_authorized_user_file(
                str(self._token_file), scopes=[GMAIL_READONLY_SCOPE]
            )
        except (OSError, ValueError) as exc:
            raise GmailNotConnectedError(
                "The saved Gmail token is invalid. Connect Gmail again."
            ) from exc

        if credentials.expired:
            if not credentials.refresh_token:
                raise GmailNotConnectedError(
                    "The Gmail session expired and cannot be refreshed. Connect Gmail again."
                )
            try:
                credentials.refresh(Request())
                self._save_credentials(credentials)
            except (RefreshError, TransportError) as exc:
                raise GmailNotConnectedError(
                    "The Gmail session could not be refreshed. Connect Gmail again."
                ) from exc

        if not credentials.valid:
            raise GmailNotConnectedError("Gmail is not connected.")
        if GMAIL_READONLY_SCOPE not in (credentials.scopes or []):
            raise GmailNotConnectedError(
                "The saved Gmail token does not have the required read-only scope."
            )
        return credentials

    def _save_credentials(self, credentials: Credentials) -> None:
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = Path(f"{self._token_file}.tmp")
        temporary_file.write_text(
            json.dumps(json.loads(credentials.to_json()), indent=2), encoding="utf-8"
        )
        temporary_file.replace(self._token_file)
