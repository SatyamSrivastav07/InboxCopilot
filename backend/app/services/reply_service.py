from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.errors import DatabaseUnavailableError, RecordNotFoundError
from app.database.models.draft import EmailDraftRecord
from app.database.repositories.draft_repository import DraftRepository
from app.database.repositories.user_scope import resolve_user_id
from app.genai.reply_chain import (
    ReplyDraftGenerator,
    normalize_reply_subject,
    validate_reply_body,
)
from app.gmail.sender import GmailSender
from app.schemas.draft import DraftSendResponse, ReplyDraft, ReplyDraftRequest
from app.services.thread_context_service import (
    ThreadContextService,
    is_no_reply_address,
)

logger = logging.getLogger(__name__)


class DraftConflictError(RuntimeError):
    """Raised for invalid or duplicate draft state transitions."""


class DraftUnsafeError(RuntimeError):
    """Raised when a draft still contains unsupported claims."""


def _analysis_context(email) -> str:
    tasks = "\n".join(
        f"- {item.title}; deadline={item.normalized_deadline or item.raw_deadline or 'unknown'}; "
        f"completed={item.completed}"
        for item in email.tasks
    ) or "None"
    meeting = (
        f"{email.meeting.title}; date={email.meeting.normalized_date or email.meeting.raw_date}; "
        f"time={email.meeting.meeting_time or 'unknown'}"
        if email.meeting
        else "None"
    )
    return (
        f"Summary: {email.summary}\n"
        f"Category: {email.category}\n"
        f"Priority: {email.priority}\n"
        f"Classification reason: {email.classification_reason}\n"
        f"Reply required: {email.reply_required}\n"
        f"Tasks:\n{tasks}\n"
        f"Meeting: {meeting}"
    )


def draft_response(
    draft: EmailDraftRecord, *, thread_message_count: int | None = None
) -> ReplyDraft:
    notes = list(draft.validation_notes or [])
    if is_no_reply_address(draft.recipient):
        notes.append("This sender appears to be a no-reply address; sending is disabled.")
    if draft.attachment_warning:
        notes.append(
            "This thread appears to request an attachment. Attachment sending is not supported."
        )
    return ReplyDraft(
        draft_id=draft.id,
        email_id=draft.email_id,
        recipient=draft.recipient,
        subject=draft.subject,
        body=draft.edited_body,
        generated_body=draft.generated_body,
        status=draft.status,
        notes=list(dict.fromkeys(notes)),
        attachment_warning=draft.attachment_warning,
        thread_message_count=thread_message_count,
        requires_user_confirmation=True,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        sent_at=draft.sent_at,
        sent_gmail_message_id=draft.sent_gmail_message_id,
    )


class ReplyService:
    def __init__(
        self,
        db: Session,
        context_service: ThreadContextService,
        generator: ReplyDraftGenerator,
        sender: GmailSender,
        user_id: int | None = None,
    ) -> None:
        self.db = db
        self.user_id = resolve_user_id(db, user_id)
        self.drafts = DraftRepository(db, self.user_id)
        self.context_service = context_service
        self.generator = generator
        self.sender = sender

    def generate(self, email_id: int, request: ReplyDraftRequest) -> ReplyDraft:
        logger.info("Reply draft generation started for email_id=%s", email_id)
        context, email = self.context_service.build(email_id)
        generated = self.generator.generate(
            thread_context=context.context,
            email_analysis=_analysis_context(email),
            instruction=request.instruction,
            tone=request.tone,
        )
        notes = list(generated.content.notes) + list(generated.validation.issues)
        draft = EmailDraftRecord(
            user_id=email.user_id,
            email_id=email.id,
            gmail_message_id=context.gmail_message_id,
            gmail_thread_id=context.gmail_thread_id,
            recipient=context.recipient,
            subject=normalize_reply_subject(context.original_subject),
            instruction=request.instruction,
            tone=request.tone.value,
            generated_body=generated.content.body.strip(),
            edited_body=generated.content.body.strip(),
            status="draft",
            in_reply_to=context.in_reply_to,
            references=context.references,
            validation_notes=notes,
            attachment_warning=context.attachment_requested,
        )
        try:
            self.drafts.add(draft)
            self.db.commit()
            self.db.refresh(draft)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DatabaseUnavailableError("The reply draft could not be saved.") from exc
        logger.info("Reply draft generation completed draft_id=%s", draft.id)
        return draft_response(draft, thread_message_count=context.message_count)

    def get(self, draft_id: int) -> ReplyDraft:
        try:
            draft = self.drafts.get(draft_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The draft could not be loaded.") from exc
        if draft is None:
            raise RecordNotFoundError("Reply draft was not found.")
        return draft_response(draft)

    def update(self, draft_id: int, body: str) -> ReplyDraft:
        draft = self._get_mutable(draft_id)
        draft.edited_body = body.strip()
        draft.status = "draft"
        draft.failure_reason = None
        validation = validate_reply_body(draft.edited_body, draft.instruction)
        draft.validation_notes = validation.issues
        self._commit(draft, "The reply draft changes could not be saved.")
        logger.info("Reply draft updated draft_id=%s", draft.id)
        return draft_response(draft)

    def approve(self, draft_id: int) -> ReplyDraft:
        draft = self._get_mutable(draft_id)
        if not draft.edited_body.strip():
            raise DraftConflictError("An empty draft cannot be approved.")
        validation = validate_reply_body(draft.edited_body, draft.instruction)
        if not validation.safe:
            draft.validation_notes = validation.issues
            self._commit(draft, "The unsafe draft state could not be saved.")
            raise DraftUnsafeError("Edit the unsupported claims before approving this draft.")
        draft.status = "approved"
        draft.validation_notes = []
        draft.failure_reason = None
        self._commit(draft, "The reply draft could not be approved.")
        logger.info("Reply draft approved draft_id=%s", draft.id)
        return draft_response(draft)

    def send(self, draft_id: int) -> DraftSendResponse:
        try:
            draft = self.drafts.get_for_update(draft_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The reply draft could not be locked for sending.") from exc
        if draft is None:
            raise RecordNotFoundError("Reply draft was not found.")
        if draft.status == "sent":
            raise DraftConflictError("This reply draft has already been sent.")
        if draft.status != "approved":
            raise DraftConflictError("Approve this draft before sending it.")
        if not draft.edited_body.strip():
            raise DraftConflictError("An empty draft cannot be sent.")
        if is_no_reply_address(draft.recipient):
            raise DraftConflictError("Sending to a no-reply address is disabled.")

        logger.info("Gmail send attempt draft_id=%s", draft.id)
        try:
            gmail_message_id = self.sender.send_reply(
                recipient=draft.recipient,
                subject=draft.subject,
                body=draft.edited_body,
                thread_id=draft.gmail_thread_id,
                in_reply_to=draft.in_reply_to,
                references=list(draft.references or []),
            )
        except Exception as exc:
            draft.status = "failed"
            draft.failure_reason = "Gmail send failed. Re-approve the draft before retrying."
            try:
                self.db.commit()
            except SQLAlchemyError:
                self.db.rollback()
            logger.exception("Gmail send failed draft_id=%s", draft.id)
            raise

        draft.status = "sent"
        draft.sent_at = datetime.now(timezone.utc)
        draft.sent_gmail_message_id = gmail_message_id
        draft.failure_reason = None
        self._commit(draft, "Gmail sent the reply, but its local status could not be saved.")
        logger.info("Gmail send succeeded draft_id=%s", draft.id)
        return DraftSendResponse(
            draft_id=draft.id,
            status="sent",
            gmail_message_id=gmail_message_id,
            sent_at=draft.sent_at,
        )

    def _get_mutable(self, draft_id: int) -> EmailDraftRecord:
        try:
            # Serialize edits/approval against send so a concurrent request
            # cannot revert a successfully sent row back to draft/approved.
            draft = self.drafts.get_for_update(draft_id)
        except SQLAlchemyError as exc:
            raise DatabaseUnavailableError("The reply draft could not be loaded.") from exc
        if draft is None:
            raise RecordNotFoundError("Reply draft was not found.")
        if draft.status == "sent":
            raise DraftConflictError("A sent draft cannot be changed or approved again.")
        return draft

    def _commit(self, draft: EmailDraftRecord, message: str) -> None:
        try:
            self.db.commit()
            self.db.refresh(draft)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DatabaseUnavailableError(message) from exc
