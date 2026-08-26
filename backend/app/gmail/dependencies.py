from functools import lru_cache

from app.config import get_settings
from app.gmail.auth import GmailAuthService
from app.gmail.client import build_gmail_client
from app.gmail.fetcher import GmailFetcher


@lru_cache
def get_gmail_auth_service() -> GmailAuthService:
    return GmailAuthService(get_settings())


def get_gmail_fetcher() -> GmailFetcher:
    # Keep OAuth/client resolution lazy so request-body validation is not masked
    # by a missing connection.
    return GmailFetcher(lambda: build_gmail_client(get_gmail_auth_service()))
