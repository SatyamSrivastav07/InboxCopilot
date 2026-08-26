import base64
from datetime import datetime, timezone
from email import message_from_bytes

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database.models.email import EmailRecord
from app.genai.reply_chain import (
    GeneratedReply,
    normalize_reply_subject,
    validate_reply_body,
)
from app.gmail.sender import GmailSender
from app.main import app
from app.schemas.draft import DraftSendResponse, DraftValidation, ReplyDraft, ReplyDraftContent, ReplyDraftRequest
from app.services.dependencies import get_reply_service
from app.services.reply_service import DraftConflictError, ReplyService
from app.services.thread_context_service import (
    ThreadContext,
    ThreadContextService,
    is_no_reply_address,
)


def make_settings(tmp_path):
    return Settings(
        mistral_api_key=None,
        mistral_model="mistral-small-latest",
        frontend_origins=("http://localhost:5173",),
        frontend_url="http://localhost:5173",
        google_client_id=None,
        google_client_secret=None,
        google_redirect_uri="http://localhost:8000/api/gmail/callback",
        gmail_token_file=tmp_path / "token.json",
        database_url=None,
        reply_thread_max_chars=10_000,
        reply_thread_recent_messages=8,
    )


def record(email_id=31, sender="Recruiter <recruiter@example.com>"):
    return EmailRecord(
        id=email_id,
        gmail_message_id=f"gmail-{email_id}",
        gmail_thread_id="thread-interview",
        sender=sender,
        recipients=["user@example.com"],
        subject="Interview Schedule",
        body_original="Can you confirm Monday at 10 AM?",
        body_cleaned="Can you confirm Monday at 10 AM?",
        received_at=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        category="meeting",
        priority="high",
        classification_reason="A meeting confirmation is requested.",
        summary="Recruiter asks about interview availability.",
        reply_required=True,
        tasks=[],
        meeting=None,
        entities=[],
    )


def gmail_payload(message_id, timestamp, sender, body, *, reply_to=None):
    encoded = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    headers = [
        {"name": "From", "value": sender},
        {"name": "To", "value": "user@example.com"},
        {"name": "Subject", "value": "Interview Schedule"},
        {"name": "Message-ID", "value": f"<{message_id}@example.com>"},
    ]
    if reply_to:
        headers.append({"name": "Reply-To", "value": reply_to})
    return {
        "id": message_id,
        "threadId": "thread-interview",
        "internalDate": str(timestamp),
        "payload": {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": encoded},
        },
    }


class ThreadFetcher:
    def __init__(self, messages):
        self.messages = messages

    def fetch_thread(self, thread_id):
        assert thread_id == "thread-interview"
        return self.messages


def test_reply_subject_normalization():
    assert normalize_reply_subject("Interview Schedule") == "Re: Interview Schedule"
    assert normalize_reply_subject("Re: Interview Schedule") == "Re: Interview Schedule"
    assert normalize_reply_subject("RE: Re: Interview Schedule") == "Re: Interview Schedule"


def test_thread_context_is_chronological_and_removes_quoted_content(db_session, tmp_path):
    source = record()
    db_session.add(source)
    db_session.commit()
    newer = gmail_payload(
        "gmail-31",
        1_725_000_200_000,
        "Recruiter <recruiter@example.com>",
        "Wednesday at 3 PM works.\n\nOn Tuesday, User wrote:\n> Is Wednesday possible?",
        reply_to="scheduling@example.com",
    )
    older = gmail_payload(
        "older",
        1_725_000_000_000,
        "Recruiter <recruiter@example.com>",
        "Can you attend Tuesday?",
    )

    context, _ = ThreadContextService(
        db_session,
        ThreadFetcher([newer, older]),
        make_settings(tmp_path),
    ).build(source.id)

    assert context.context.index("Can you attend Tuesday?") < context.context.index("Wednesday at 3 PM works.")
    assert "Is Wednesday possible?" not in context.context
    assert context.recipient == "scheduling@example.com"
    assert context.in_reply_to == "<gmail-31@example.com>"
    assert context.message_count == 2


class FakeContextService:
    def __init__(self, source, *, recipient="recruiter@example.com"):
        self.source = source
        self.context = ThreadContext(
            email_id=source.id,
            gmail_message_id=source.gmail_message_id,
            gmail_thread_id=source.gmail_thread_id,
            recipient=recipient,
            original_subject=source.subject,
            in_reply_to="<source@example.com>",
            references=["<older@example.com>", "<source@example.com>"],
            context="Recruiter proposed Monday at 10 AM.",
            message_count=3,
            automated_sender=is_no_reply_address(recipient),
            attachment_requested=False,
        )

    def build(self, email_id):
        assert email_id == self.source.id
        return self.context, self.source


class FakeGenerator:
    def generate(self, **kwargs):
        return GeneratedReply(
            content=ReplyDraftContent(
                body="Thank you. I will confirm my availability shortly.",
                notes=[],
            ),
            validation=DraftValidation(safe=True, issues=[]),
        )


class FakeSender:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def send_reply(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return "sent-gmail-id"


def reply_service(db_session, source, *, sender=None, recipient="recruiter@example.com"):
    return ReplyService(
        db_session,
        FakeContextService(source, recipient=recipient),
        FakeGenerator(),
        sender or FakeSender(),
    )


def test_draft_persistence_editing_approval_and_exact_text_send(db_session):
    source = record()
    db_session.add(source)
    db_session.commit()
    gmail_sender = FakeSender()
    service = reply_service(db_session, source, sender=gmail_sender)

    draft = service.generate(source.id, ReplyDraftRequest())
    generated_text = draft.generated_body
    edited_text = "Thank you. Thursday afternoon would work better; is that available?"
    edited = service.update(draft.draft_id, edited_text)

    assert edited.generated_body == generated_text
    assert edited.body == edited_text
    with pytest.raises(DraftConflictError, match="Approve"):
        service.send(draft.draft_id)

    approved = service.approve(draft.draft_id)
    sent = service.send(draft.draft_id)

    assert approved.status == "approved"
    assert sent.status == "sent"
    assert gmail_sender.calls[0]["body"] == edited_text
    assert gmail_sender.calls[0]["thread_id"] == "thread-interview"
    with pytest.raises(DraftConflictError, match="already been sent"):
        service.send(draft.draft_id)


def test_send_failure_records_failed_state(db_session):
    source = record()
    db_session.add(source)
    db_session.commit()
    service = reply_service(
        db_session, source, sender=FakeSender(RuntimeError("provider failed"))
    )
    draft = service.generate(source.id, ReplyDraftRequest())
    service.approve(draft.draft_id)

    with pytest.raises(RuntimeError, match="provider failed"):
        service.send(draft.draft_id)

    assert service.get(draft.draft_id).status == "failed"


def test_no_reply_detection_and_send_block(db_session):
    source = record(sender="No Reply <no-reply@example.com>")
    db_session.add(source)
    db_session.commit()
    service = reply_service(db_session, source, recipient="no-reply@example.com")
    draft = service.generate(source.id, ReplyDraftRequest())
    service.approve(draft.draft_id)

    assert is_no_reply_address("noreply@example.com")
    assert is_no_reply_address("do-not-reply@example.com")
    with pytest.raises(DraftConflictError, match="no-reply"):
        service.send(draft.draft_id)


@pytest.mark.parametrize(
    "body, instruction, expected_issue",
    [
        ("I have attached the requested PDF.", None, "attachment"),
        ("I completed the assessment.", None, "complete"),
        ("Monday at 10 works for me.", None, "commitment"),
    ],
)
def test_unsupported_commitment_validator(body, instruction, expected_issue):
    result = validate_reply_body(body, instruction)
    assert result.safe is False
    assert any(expected_issue in issue.lower() for issue in result.issues)


def test_explicit_accept_instruction_allows_commitment():
    result = validate_reply_body(
        "Monday at 10 works for me.", "Accept the meeting."
    )
    assert result.safe is True


class ExecuteRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class MessagesResource:
    def __init__(self):
        self.body = None

    def send(self, *, userId, body):
        assert userId == "me"
        self.body = body
        return ExecuteRequest({"id": "gmail-sent-1"})


class GmailService:
    def __init__(self):
        self.messages_resource = MessagesResource()

    def users(self):
        return self

    def messages(self):
        return self.messages_resource


def test_gmail_sender_builds_threaded_mime_message():
    gmail = GmailService()
    message_id = GmailSender(gmail).send_reply(
        recipient="recruiter@example.com",
        subject="Re: Interview Schedule",
        body="Thursday works better. Is that available?",
        thread_id="thread-interview",
        in_reply_to="<source@example.com>",
        references=["<older@example.com>", "<source@example.com>"],
    )

    request_body = gmail.messages_resource.body
    parsed = message_from_bytes(base64.urlsafe_b64decode(request_body["raw"]))
    assert message_id == "gmail-sent-1"
    assert request_body["threadId"] == "thread-interview"
    assert parsed["To"] == "recruiter@example.com"
    assert parsed["In-Reply-To"] == "<source@example.com>"
    assert "Thursday works better" in parsed.get_payload(decode=True).decode()


class StubReplyAPIService:
    def _draft(self, body="Draft body", status="draft"):
        now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        return ReplyDraft(
            draft_id=91,
            email_id=31,
            recipient="recruiter@example.com",
            subject="Re: Interview Schedule",
            body=body,
            generated_body="Draft body",
            status=status,
            requires_user_confirmation=True,
            created_at=now,
            updated_at=now,
        )

    def generate(self, email_id, request):
        assert email_id == 31
        return self._draft()

    def get(self, draft_id):
        return self._draft()

    def update(self, draft_id, body):
        return self._draft(body=body)

    def approve(self, draft_id):
        return self._draft(status="approved")

    def send(self, draft_id):
        now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        return DraftSendResponse(
            draft_id=draft_id,
            status="sent",
            gmail_message_id="gmail-sent-1",
            sent_at=now,
        )


def test_reply_draft_api_exposes_separate_generate_edit_approve_send_steps():
    app.dependency_overrides[get_reply_service] = lambda: StubReplyAPIService()
    client = TestClient(app)
    try:
        generated = client.post(
            "/api/emails/31/draft-reply",
            json={"instruction": "Ask about Thursday", "tone": "professional"},
        )
        edited = client.patch("/api/drafts/91", json={"body": "Edited exact text"})
        approved = client.post("/api/drafts/91/approve")
        sent = client.post("/api/drafts/91/send")
    finally:
        app.dependency_overrides.clear()

    assert generated.status_code == 200
    assert generated.json()["requires_user_confirmation"] is True
    assert edited.json()["body"] == "Edited exact text"
    assert approved.json()["status"] == "approved"
    assert sent.json()["status"] == "sent"
