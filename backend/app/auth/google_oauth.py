from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, MutableMapping

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2 import OAuth2Error

from app.config import Settings
from app.gmail.auth import GMAIL_SCOPES, OAUTH_STATE_TTL_SECONDS
from app.gmail.errors import GmailOAuthError

_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_OAUTH_SESSION_KEY = "google_oauth_pending"


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    display_name: str | None
    avatar_url: str | None


class GoogleOAuthService:
    """OAuth/PKCE exchange bound to the browser's signed session cookie."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client_config(self) -> dict[str, object]:
        client_id, client_secret = self.settings.require_google_oauth()
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.settings.google_redirect_uri],
            }
        }

    def _flow(self, state: str | None = None) -> Flow:
        flow = Flow.from_client_config(self._client_config(), scopes=GMAIL_SCOPES, state=state)
        flow.redirect_uri = self.settings.google_redirect_uri
        return flow

    def authorization_url(self, browser_session: MutableMapping[str, Any]) -> str:
        state = secrets.token_urlsafe(32)
        flow = self._flow(state=state)
        url, returned_state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        browser_session[_OAUTH_SESSION_KEY] = {
            "state": returned_state,
            "code_verifier": flow.code_verifier or "",
            "issued_at": time.time(),
        }
        return url

    def exchange_code(
        self, code: str, state: str, browser_session: MutableMapping[str, Any]
    ) -> Credentials:
        pending = browser_session.pop(_OAUTH_SESSION_KEY, None)
        if not isinstance(pending, dict) or pending.get("state") != state:
            raise GmailOAuthError("The OAuth state is invalid or expired. Start the connection again.")
        issued_at = pending.get("issued_at")
        if not isinstance(issued_at, (int, float)) or time.time() - issued_at >= OAUTH_STATE_TTL_SECONDS:
            raise GmailOAuthError("The OAuth state is invalid or expired. Start the connection again.")
        code_verifier = pending.get("code_verifier")
        if not isinstance(code_verifier, str) or not code_verifier:
            raise GmailOAuthError("The OAuth PKCE verifier is missing. Start the connection again.")
        try:
            flow = self._flow(state=state)
            flow.code_verifier = code_verifier
            flow.fetch_token(code=code)
            return flow.credentials
        except OAuth2Error as exc:
            error_code = getattr(exc, "error", None) or exc.__class__.__name__
            description = getattr(exc, "description", None) or "Token exchange was rejected."
            raise GmailOAuthError(f"Google OAuth failed: {error_code}. {description}") from exc
        except GmailOAuthError:
            raise
        except Exception as exc:
            raise GmailOAuthError(
                "Google OAuth could not be completed. Check the redirect URI and try again."
            ) from exc

    def identity(self, credentials: Credentials) -> GoogleIdentity:
        try:
            response = AuthorizedSession(credentials).get(_USERINFO_URL, timeout=10)
            response.raise_for_status()
            payload = response.json()
            subject = str(payload.get("sub") or "")
            email = str(payload.get("email") or "")
            if not subject or not email:
                raise ValueError("Google did not provide a user identity.")
            return GoogleIdentity(
                subject=subject,
                email=email,
                display_name=str(payload["name"]) if payload.get("name") else None,
                avatar_url=str(payload["picture"]) if payload.get("picture") else None,
            )
        except Exception as exc:
            raise GmailOAuthError(
                "Google account identity could not be verified. Please try connecting again."
            ) from exc
