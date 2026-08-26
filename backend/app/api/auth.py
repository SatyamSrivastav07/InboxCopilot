from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.google_oauth import GoogleOAuthService
from app.auth.schemas import GoogleAuthUrl, SessionStatus, SessionUser
from app.config import get_settings
from app.database.dependencies import get_db
from app.database.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/session", response_model=SessionStatus)
def session_status(request: Request, db: Annotated[Session, Depends(get_db)]) -> SessionStatus:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return SessionStatus(authenticated=False)
    user = UserRepository(db).get(user_id)
    if user is None or user.status != "active":
        request.session.clear()
        return SessionStatus(authenticated=False)
    return SessionStatus(
        authenticated=True,
        user=SessionUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        ),
    )


@router.get("/google", response_model=GoogleAuthUrl)
def begin_google_auth(request: Request) -> GoogleAuthUrl:
    return GoogleAuthUrl(
        authorization_url=GoogleOAuthService(get_settings()).authorization_url(request.session)
    )


@router.post("/logout", response_model=SessionStatus)
def logout(_user: CurrentUser, request: Request) -> SessionStatus:
    request.session.clear()
    return SessionStatus(authenticated=False)
