from fastapi.testclient import TestClient

from app.genai.analyzer import get_email_analyzer
from app.main import app
from app.schemas.email import EmailAnalysis


class StubAnalyzer:
    def analyze(self, email):
        return EmailAnalysis(
            sender=email.sender,
            subject=email.subject,
            summary="HR needs signed documents and an onboarding confirmation.",
            classification={
                "category": "action_required",
                "priority": "high",
                "reason": "The sender requests documents by a deadline.",
            },
            tasks=[
                {
                    "title": "Send signed joining documents",
                    "description": "Send the requested signed documents to HR.",
                    "raw_deadline": "Friday",
                    "normalized_deadline": None,
                }
            ],
            meeting={
                "title": "Onboarding",
                "date": "Monday",
                "time": "10:00",
                "participants": [],
                "location_or_link": None,
            },
            entities={
                "people": [],
                "organizations": ["HR"],
                "dates": ["Friday", "Monday"],
                "locations": [],
            },
            reply_required=True,
        )


def test_analyze_email_returns_structured_analysis():
    app.dependency_overrides[get_email_analyzer] = lambda: StubAnalyzer()
    client = TestClient(app)
    response = client.post(
        "/api/analyze-email",
        json={
            "sender": "hr@example.com",
            "subject": "Joining Documents",
            "body": "Please send your signed documents by Friday.",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["classification"]["category"] == "action_required"
    assert response.json()["reply_required"] is True


def test_analyze_email_validates_empty_input():
    client = TestClient(app)
    response = client.post(
        "/api/analyze-email", json={"sender": "", "subject": "", "body": ""}
    )
    assert response.status_code == 422

