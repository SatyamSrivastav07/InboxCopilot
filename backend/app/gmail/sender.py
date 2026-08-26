from __future__ import annotations

import base64
from collections.abc import Callable
from email.message import EmailMessage

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from app.gmail.fetcher import translate_http_error


class GmailSender:
    def __init__(self, service: Resource | Callable[[], Resource]) -> None:
        self._service_or_factory = service

    def _service(self) -> Resource:
        if callable(self._service_or_factory):
            self._service_or_factory = self._service_or_factory()
        return self._service_or_factory

    def send_reply(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        thread_id: str,
        in_reply_to: str | None,
        references: list[str],
    ) -> str | None:
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = " ".join(references)
        message.set_content(body)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        try:
            response = (
                self._service()
                .users()
                .messages()
                .send(
                    userId="me",
                    body={"raw": encoded, "threadId": thread_id},
                )
                .execute()
            )
        except HttpError as exc:
            raise translate_http_error(exc) from exc
        return str(response.get("id")) if response.get("id") else None
