from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.errors import DatabaseUnavailableError, RecordNotFoundError
from app.database.repositories.email_repository import EmailRepository
from app.gmail.fetcher import GmailFetcher
from app.gmail.parser import parse_gmail_message
from app.gmail.schemas import GmailEmail


class ThreadContextError(RuntimeError):
    """Raised when a safe reply target/thread cannot be prepared."""


@dataclass(frozen=True)
class ThreadContext:
    email_id: int
    gmail_message_id: str
    gmail_thread_id: str
    recipient: str
    original_subject: str
    in_reply_to: str | None
    references: list[str]
    context: str
    message_count: int
    automated_sender: bool
    attachment_requested: bool


_ORIGINAL_MESSAGE = re.compile(
    r"^(?:-{2,}\s*original message\s*-{2,}|on .+ wrote:)$", re.IGNORECASE
)
_ATTACHMENT_REQUEST = re.compile(
    r"\b(attach(?:ed|ment)?|send|provide|share|upload)\b.{0,50}\b(pdf|document|file|resume|cv|form)\b",
    re.IGNORECASE | re.DOTALL,
)


def strip_quoted_content(body: str) -> str:
    kept: list[str] = []
    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if _ORIGINAL_MESSAGE.match(stripped):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def is_no_reply_address(address: str) -> bool:
    local = address.split("@", 1)[0].lower().replace("_", "-")
    compact = local.replace("-", "")
    return compact.startswith("noreply") or compact.startswith("donotreply")


def _timestamp(message: GmailEmail) -> datetime:
    value = message.received_at
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


class ThreadContextService:
    def __init__(
        self,
        db: Session,
        fetcher: GmailFetcher,
        settings: Settings,
    ) -> None:
        self.emails = EmailRepository(db)
        self.fetcher = fetcher
        self.settings = settings

    def build(self, email_id: int) -> tuple[ThreadContext, object]:
        try:
            record = self.emails.get_by_id(email_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The database is unavailable.") from exc
        if record is None:
            raise RecordNotFoundError("Persisted email was not found.")

        raw_messages = self.fetcher.fetch_thread(record.gmail_thread_id)
        messages: list[GmailEmail] = []
        for raw in raw_messages:
            try:
                messages.append(parse_gmail_message(raw))
            except Exception:
                continue
        if not messages:
            raise ThreadContextError("The Gmail thread could not be loaded.")
        messages.sort(key=_timestamp)

        target = next(
            (item for item in messages if item.message_id == record.gmail_message_id),
            None,
        )
        if target is None:
            raise ThreadContextError(
                "The source message is no longer available in its Gmail thread."
            )

        _, recipient = parseaddr(target.reply_to or target.sender)
        if not recipient or "@" not in recipient:
            raise ThreadContextError("The source email does not contain a valid reply address.")

        recent = messages[-self.settings.reply_thread_recent_messages :]
        blocks: list[str] = []
        for index, message in enumerate(recent, start=max(1, len(messages) - len(recent) + 1)):
            clean_body = strip_quoted_content(message.body)
            blocks.append(
                f"[Message {index}]\n"
                f"Sender: {message.sender or 'Unknown'}\n"
                f"Timestamp: {_timestamp(message).isoformat()}\n"
                f"Subject: {message.subject}\n"
                f"Body:\n{clean_body or '(No usable text)'}"
            )

        selected: list[str] = []
        used = 0
        for block in reversed(blocks):
            remaining = self.settings.reply_thread_max_chars - used
            if remaining <= 0:
                break
            selected.append(block if len(block) <= remaining else block[:remaining])
            used += min(len(block), remaining) + 2
        selected.reverse()
        omitted = len(messages) - len(selected)
        prefix = f"[{omitted} earlier messages omitted for context limits]\n\n" if omitted else ""
        context_text = prefix + "\n\n".join(selected)

        references = list(dict.fromkeys(target.references))
        if target.internet_message_id and target.internet_message_id not in references:
            references.append(target.internet_message_id)

        return (
            ThreadContext(
                email_id=record.id,
                gmail_message_id=record.gmail_message_id,
                gmail_thread_id=record.gmail_thread_id,
                recipient=recipient,
                original_subject=record.subject,
                in_reply_to=target.internet_message_id,
                references=references,
                context=context_text,
                message_count=len(messages),
                automated_sender=is_no_reply_address(recipient),
                attachment_requested=bool(_ATTACHMENT_REQUEST.search(context_text)),
            ),
            record,
        )
