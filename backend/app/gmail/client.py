from __future__ import annotations

from googleapiclient.discovery import Resource, build

from app.gmail.auth import GmailAuthService


def build_gmail_client(auth_service: GmailAuthService) -> Resource:
    return build(
        "gmail",
        "v1",
        credentials=auth_service.get_credentials(),
        cache_discovery=False,
    )

