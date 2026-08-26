from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.config import get_settings
from app.gmail.client import build_gmail_client
from app.gmail.fetcher import GmailFetcher
from app.gmail.sender import GmailSender
from app.gmail.user_auth import UserGmailAuthService
from app.database.dependencies import get_db


def get_gmail_auth_service(
    db: Annotated[Session, Depends(get_db)],
    user: CurrentUser,
) -> UserGmailAuthService:
    return UserGmailAuthService(db, user.id, get_settings())


def get_gmail_fetcher(
    auth: Annotated[UserGmailAuthService, Depends(get_gmail_auth_service)],
) -> GmailFetcher:
    # Keep OAuth/client resolution lazy so request-body validation is not masked
    # by a missing connection.
    return GmailFetcher(lambda: build_gmail_client(auth))


def get_gmail_sender(
    auth: Annotated[UserGmailAuthService, Depends(get_gmail_auth_service)],
) -> GmailSender:
    return GmailSender(lambda: build_gmail_client(auth))
