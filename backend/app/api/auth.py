from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.google_oauth import GoogleOAuthService
from app.auth.schemas import (
    AccountDeletionRequest,
    AccountDeletionStatus,
    GoogleAuthUrl,
    SessionStatus,
    SessionUser,
)
from app.config import get_settings
from app.database.dependencies import get_db
from app.database.repositories.user_repository import UserRepository
from app.vectorstore.dependencies import get_vector_store
from app.vectorstore.store import ChromaStore

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


@router.delete("/account", response_model=AccountDeletionStatus)
def delete_account(
    payload: AccountDeletionRequest,
    request: Request,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    vector_store: Annotated[ChromaStore, Depends(get_vector_store)],
) -> AccountDeletionStatus:
    """Permanently clear a user's local account and all locally stored inbox data."""
    del payload  # Literal validation above makes destructive intent explicit.
    stored_user = UserRepository(db).get(user.id)
    if stored_user is None:
        request.session.clear()
        return AccountDeletionStatus(deleted=True)

    # Remove derived semantic content first. If this step fails, do not delete
    # the durable account record so the user can retry the complete deletion.
    vector_store.delete_user(stored_user.id)
    db.delete(stored_user)
    db.commit()
    request.session.clear()
    return AccountDeletionStatus(deleted=True)
