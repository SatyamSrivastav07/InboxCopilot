import base64

import pytest

from app.gmail.parser import parse_gmail_message


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def message(payload, *, message_id="message-1", labels=None):
    return {
        "id": message_id,
        "threadId": "thread-1",
        "internalDate": "1735689600000",
        "labelIds": labels or ["INBOX"],
        "payload": {
            "headers": [
                {"name": "From", "value": "Example Person <person@example.com>"},
                {"name": "To", "value": "User <user@example.com>"},
                {"name": "Cc", "value": "Team <team@example.com>"},
                {"name": "Subject", "value": "Safe test email"},
            ],
            **payload,
        },
    }


@pytest.fixture
def plain_text_payload():
    return message({"mimeType": "text/plain", "body": {"data": encoded("Hello from plain text.")}})


@pytest.fixture
def html_only_payload():
    return message({"mimeType": "text/html", "body": {"data": encoded("<p>Hello <strong>from HTML</strong>.</p><script>ignore()</script>")}})


@pytest.fixture
def multipart_alternative_payload():
    return message(
        {
            "mimeType": "multipart/alternative",
            "body": {},
            "parts": [
                {"mimeType": "text/html", "body": {"data": encoded("<p>HTML fallback</p>")}},
                {"mimeType": "text/plain", "body": {"data": encoded("Preferred plain body")}},
            ],
        }
    )


@pytest.fixture
def attachment_payload():
    return message(
        {
            "mimeType": "multipart/mixed",
            "body": {},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "body": {},
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": encoded("Nested email body")}},
                        {"mimeType": "text/html", "body": {"data": encoded("<p>Nested HTML</p>")}},
                    ],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "private-document.pdf",
                    "body": {"attachmentId": "attachment-1", "size": 1200},
                },
            ],
        }
    )


@pytest.fixture
def empty_body_payload():
    return message({"mimeType": "multipart/mixed", "body": {}, "parts": []})


def test_parses_plain_text_email(plain_text_payload):
    parsed = parse_gmail_message(plain_text_payload)
    assert parsed.body == "Hello from plain text."
    assert parsed.sender == "Example Person <person@example.com>"
    assert parsed.recipients == ["User <user@example.com>", "Team <team@example.com>"]
    assert parsed.subject == "Safe test email"
    assert parsed.received_at.isoformat() == "2025-01-01T00:00:00+00:00"


def test_converts_html_only_email_to_clean_text(html_only_payload):
    parsed = parse_gmail_message(html_only_payload)
    assert parsed.body == "Hello\nfrom HTML\n."
    assert "ignore" not in parsed.body


def test_prefers_plain_text_in_multipart_alternative(multipart_alternative_payload):
    assert parse_gmail_message(multipart_alternative_payload).body == "Preferred plain body"


def test_ignores_attachment_and_handles_nested_multipart(attachment_payload):
    parsed = parse_gmail_message(attachment_payload)
    assert parsed.body == "Nested email body"
    assert "private-document" not in parsed.body


def test_handles_empty_body(empty_body_payload):
    assert parse_gmail_message(empty_body_payload).body == ""

