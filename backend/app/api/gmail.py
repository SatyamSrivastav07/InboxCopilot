from __future__ import annotations

import logging
import json
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.google_oauth import GoogleOAuthService
from app.config import ConfigurationError, get_settings
from app.database.dependencies import get_db
from app.database.repositories.gmail_connection_repository import GmailConnectionRepository
from app.database.repositories.user_repository import UserRepository
from app.security.token_cipher import OAuthTokenCipher
from app.services.gmail_connection_service import GmailConnectionService
from app.gmail.auth import GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE
from app.gmail.dependencies import get_gmail_auth_service, get_gmail_fetcher
from app.gmail.errors import GmailError, GmailNotConnectedError, GmailParseError
from app.gmail.user_auth import UserGmailAuthService
from app.gmail.fetcher import GmailFetcher
from app.gmail.parser import parse_gmail_message
from app.gmail.schemas import (
    GmailAuthUrl,
    GmailEmail,
    GmailStatus,
    GmailSyncRequest,
)
from app.cache.keys import gmail_sync_lock_key
from app.schemas.jobs import JobQueued, JobState
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService
from app.services.inline_jobs import run_inline_gmail_sync
from app.security.rate_limit_dependencies import limit_inbox_sync

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/status", response_model=GmailStatus)
def gmail_status(
    user: CurrentUser,
    auth: Annotated[UserGmailAuthService, Depends(get_gmail_auth_service)],
) -> GmailStatus:
    try:
        credentials = auth.get_credentials()
    except GmailNotConnectedError:
        return GmailStatus(connected=False, can_read=False, can_send=False)

    granted_scopes = set(credentials.scopes or [])
    return GmailStatus(
        connected=True,
        can_read=GMAIL_READONLY_SCOPE in granted_scopes,
        can_send=GMAIL_SEND_SCOPE in granted_scopes,
    )


@router.delete("/connection", status_code=204)
def disconnect_gmail(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if GmailConnectionRepository(db).delete_for_user(user.id):
        db.commit()


@router.get("/auth-url", response_model=GmailAuthUrl)
def gmail_auth_url(request: Request) -> GmailAuthUrl:
    return GmailAuthUrl(
        authorization_url=GoogleOAuthService(get_settings()).authorization_url(request.session)
    )


@router.get("/callback", response_class=RedirectResponse)
def gmail_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    frontend_url = get_settings().frontend_url
    if error:
        query = urlencode({"gmail": "error", "reason": "Google authorization was cancelled."})
        return RedirectResponse(f"{frontend_url}/gmail?{query}")
    if not code or not state:
        query = urlencode({"gmail": "error", "reason": "OAuth callback data is incomplete."})
        return RedirectResponse(f"{frontend_url}/gmail?{query}")
    try:
        oauth = GoogleOAuthService(get_settings())
        credentials = oauth.exchange_code(code=code, state=state, browser_session=request.session)
        identity = oauth.identity(credentials)
        user = UserRepository(db).get_or_create_google_user(
            google_subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
        )
        GmailConnectionService(db, OAuthTokenCipher.from_settings(get_settings())).save_credentials(
            user.id,
            json.loads(credentials.to_json()),
            google_email=identity.email,
        )
        request.session.clear()
        request.session["user_id"] = user.id
    except (ConfigurationError, GmailError, ValueError) as exc:
        query = urlencode({"gmail": "error", "reason": str(exc)})
        return RedirectResponse(f"{frontend_url}/gmail?{query}")
    return RedirectResponse(f"{frontend_url}/gmail?gmail=connected")


@router.get("/emails", response_model=list[GmailEmail])
def gmail_emails(
    _user: CurrentUser,
    fetcher: Annotated[GmailFetcher, Depends(get_gmail_fetcher)],
    limit: int = Query(default=20, ge=1, le=50),
    unread_only: bool = Query(default=False),
) -> list[GmailEmail]:
    parsed: list[GmailEmail] = []
    for payload in fetcher.fetch_recent(limit=limit, unread_only=unread_only):
        try:
            parsed.append(parse_gmail_message(payload))
        except GmailParseError:
            logger.warning("Skipping malformed Gmail message", exc_info=True)
    return parsed


@router.get("/emails/{message_id}", response_model=GmailEmail)
def gmail_email(
    message_id: str,
    _user: CurrentUser,
    fetcher: Annotated[GmailFetcher, Depends(get_gmail_fetcher)],
) -> GmailEmail:
    return parse_gmail_message(fetcher.fetch_message(message_id))


@router.post("/sync", response_model=JobQueued | JobState, status_code=202)
def sync_gmail(
    request: GmailSyncRequest,
    http_request: Request,
    response: Response,
    user: CurrentUser,
    _rate_limit: Annotated[None, Depends(limit_inbox_sync)],
    jobs: Annotated[JobService, Depends(get_job_service)],
) -> JobQueued | JobState:
    if get_settings().sync_execution_mode == "request":
        response.status_code = status.HTTP_200_OK
        return run_inline_gmail_sync(user_id=user.id, request=request)
    return jobs.enqueue(
        "app.workers.gmail_tasks.sync_gmail",
        kwargs={"user_id": user.id, "limit": request.limit, "unread_only": request.unread_only},
        lock_key=gmail_sync_lock_key(user.id),
        user_id=user.id,
        request_id=getattr(http_request.state, "request_id", None),
    )
