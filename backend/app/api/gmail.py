from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.gmail.auth import GMAIL_READONLY_SCOPE, GMAIL_SEND_SCOPE, GmailAuthService
from app.gmail.dependencies import get_gmail_auth_service, get_gmail_fetcher
from app.gmail.errors import GmailError, GmailNotConnectedError, GmailParseError
from app.gmail.fetcher import GmailFetcher
from app.gmail.parser import parse_gmail_message
from app.gmail.schemas import (
    GmailAuthUrl,
    GmailEmail,
    GmailStatus,
    GmailSyncRequest,
    GmailSyncResponse,
)
from app.services.dependencies import get_gmail_sync_service
from app.services.gmail_sync import GmailSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/status", response_model=GmailStatus)
def gmail_status(
    auth: Annotated[GmailAuthService, Depends(get_gmail_auth_service)],
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


@router.get("/auth-url", response_model=GmailAuthUrl)
def gmail_auth_url(
    auth: Annotated[GmailAuthService, Depends(get_gmail_auth_service)],
) -> GmailAuthUrl:
    return GmailAuthUrl(authorization_url=auth.authorization_url())


@router.get("/callback", response_class=RedirectResponse)
def gmail_callback(
    auth: Annotated[GmailAuthService, Depends(get_gmail_auth_service)],
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
        auth.exchange_code(code=code, state=state)
    except GmailError as exc:
        query = urlencode({"gmail": "error", "reason": str(exc)})
        return RedirectResponse(f"{frontend_url}/gmail?{query}")
    return RedirectResponse(f"{frontend_url}/gmail?gmail=connected")


@router.get("/emails", response_model=list[GmailEmail])
def gmail_emails(
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
    fetcher: Annotated[GmailFetcher, Depends(get_gmail_fetcher)],
) -> GmailEmail:
    return parse_gmail_message(fetcher.fetch_message(message_id))


@router.post("/sync", response_model=GmailSyncResponse)
def sync_gmail(
    request: GmailSyncRequest,
    sync_service: Annotated[GmailSyncService, Depends(get_gmail_sync_service)],
) -> GmailSyncResponse:
    return sync_service.sync(request)
