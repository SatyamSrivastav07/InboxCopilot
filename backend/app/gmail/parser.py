from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup

from app.gmail.errors import GmailParseError
from app.gmail.schemas import GmailEmail


def _decode_data(data: str | None) -> str:
    if not data:
        return ""
    try:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, TypeError) as exc:
        raise GmailParseError("Email body contains invalid encoded data.") from exc


def _clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in value.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _html_to_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return _clean_text(soup.get_text(separator="\n"))


def _collect_bodies(part: dict[str, Any]) -> tuple[list[str], list[str]]:
    plain: list[str] = []
    html: list[str] = []
    mime_type = str(part.get("mimeType", "")).lower()
    filename = part.get("filename") or ""
    body = part.get("body") or {}

    # Attachment parts can contain binary data; Phase 2 intentionally ignores them.
    if not filename and not body.get("attachmentId"):
        decoded = _decode_data(body.get("data"))
        if decoded:
            if mime_type == "text/plain":
                plain.append(_clean_text(decoded))
            elif mime_type == "text/html":
                html.append(_html_to_text(decoded))

    for child in part.get("parts") or []:
        child_plain, child_html = _collect_bodies(child)
        plain.extend(child_plain)
        html.extend(child_html)
    return plain, html


def _header_map(payload: dict[str, Any]) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for item in payload.get("headers") or []:
        name = str(item.get("name", "")).casefold()
        value = str(item.get("value", ""))
        if name:
            headers.setdefault(name, []).append(value)
    return headers


def _recipients(headers: dict[str, list[str]]) -> list[str]:
    raw_values = [
        value
        for name in ("to", "cc", "bcc")
        for value in headers.get(name, [])
    ]
    recipients: list[str] = []
    for display_name, address in getaddresses(raw_values):
        value = f"{display_name} <{address}>" if display_name and address else address or display_name
        if value and value not in recipients:
            recipients.append(value)
    return recipients


def _received_at(message: dict[str, Any], headers: dict[str, list[str]]) -> datetime | str:
    internal_date = message.get("internalDate")
    if internal_date:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    date_value = next(iter(headers.get("date", [])), "")
    if date_value:
        try:
            parsed = parsedate_to_datetime(date_value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return date_value
    return ""


def parse_gmail_message(message: dict[str, Any]) -> GmailEmail:
    message_id = str(message.get("id") or "")
    thread_id = str(message.get("threadId") or "")
    if not message_id or not thread_id:
        raise GmailParseError("Gmail message is missing its message or thread ID.")

    payload = message.get("payload") or {}
    headers = _header_map(payload)
    plain_bodies, html_bodies = _collect_bodies(payload)
    usable_plain = [body for body in plain_bodies if body]
    usable_html = [body for body in html_bodies if body]
    body = "\n\n".join(usable_plain or usable_html).strip()

    return GmailEmail(
        message_id=message_id,
        thread_id=thread_id,
        sender=next(iter(headers.get("from", [])), ""),
        recipients=_recipients(headers),
        subject=next(iter(headers.get("subject", [])), "(No subject)"),
        body=body,
        received_at=_received_at(message, headers),
        labels=[str(label) for label in message.get("labelIds") or []],
    )

