from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from app.gmail.errors import GmailAPIError, GmailRateLimitError


def translate_http_error(exc: HttpError) -> GmailAPIError:
    status_code = getattr(exc.resp, "status", None)
    try:
        payload = json.loads(exc.content.decode("utf-8", errors="replace"))
        reasons = {
            item.get("reason")
            for item in payload.get("error", {}).get("errors", [])
            if item.get("reason")
        }
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        reasons = set()

    if "accessNotConfigured" in reasons:
        return GmailAPIError(
            "Gmail API is not enabled for this Google Cloud project. Enable it, "
            "wait a few minutes, and try again."
        )
    if "insufficientPermissions" in reasons:
        return GmailAPIError(
            "The Gmail connection is missing required permission. Delete token.json "
            "and connect Gmail again."
        )
    rate_limit_reasons = {
        "rateLimitExceeded",
        "userRateLimitExceeded",
        "dailyLimitExceeded",
        "quotaExceeded",
    }
    if status_code == 429 or reasons.intersection(rate_limit_reasons):
        return GmailRateLimitError(
            "Gmail rate limit or quota was reached. Wait a moment and try again."
        )
    return GmailAPIError("The Gmail API is unavailable. Please try again.")


class GmailFetcher:
    def __init__(self, service: Resource | Callable[[], Resource]) -> None:
        self._service_or_factory = service

    def _service(self) -> Resource:
        if callable(self._service_or_factory):
            self._service_or_factory = self._service_or_factory()
        return self._service_or_factory

    def list_message_ids(self, limit: int = 20, unread_only: bool = False) -> list[str]:
        try:
            request = self._service().users().messages().list(
                userId="me",
                labelIds=["INBOX"],
                q="is:unread" if unread_only else None,
                maxResults=limit,
            )
            response = request.execute()
            return [item["id"] for item in response.get("messages", []) if item.get("id")]
        except HttpError as exc:
            raise translate_http_error(exc) from exc

    def fetch_recent(self, limit: int = 20, unread_only: bool = False) -> list[dict[str, Any]]:
        return [
            self.fetch_message(message_id)
            for message_id in self.list_message_ids(limit=limit, unread_only=unread_only)
        ]

    def fetch_unread(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.fetch_recent(limit=limit, unread_only=True)

    def fetch_message(self, message_id: str) -> dict[str, Any]:
        try:
            return (
                self._service().users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
        except HttpError as exc:
            raise translate_http_error(exc) from exc

    def fetch_thread(self, thread_id: str) -> list[dict[str, Any]]:
        try:
            thread = (
                self._service().users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
            return thread.get("messages", [])
        except HttpError as exc:
            raise translate_http_error(exc) from exc
