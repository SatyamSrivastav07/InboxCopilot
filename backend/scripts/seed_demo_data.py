"""Seed clearly labelled synthetic inbox data for a safe product demo.

This does not contact Gmail or Mistral. Use the normal background reindex endpoint
afterwards if semantic search is needed and a Mistral key is configured.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.database.session import get_session_factory
from app.gmail.schemas import GmailEmail
from app.schemas.email import EmailAnalysis
from app.services.email_persistence import EmailPersistenceService


DEMO_EMAILS = [
    {
        "id": "demo-urgent-launch",
        "sender": "Maya Chen <maya@example.test>",
        "subject": "[Demo] Production launch checklist — action needed",
        "body": "Synthetic demo email. Please review the launch checklist and confirm the rollback owner by 2026-09-01.",
        "category": "action_required", "priority": "urgent", "reply_required": True,
        "tasks": [{"title": "Confirm rollback owner", "description": "Review launch checklist", "normalized_deadline": "2026-09-01"}],
    },
    {
        "id": "demo-onboarding",
        "sender": "HR Team <hr@example.test>",
        "subject": "[Demo] Onboarding documents",
        "body": "Synthetic demo email. HR requested onboarding documents and asked for a reply confirming receipt.",
        "category": "needs_reply", "priority": "high", "reply_required": True, "tasks": [],
    },
    {
        "id": "demo-planning",
        "sender": "Jordan Lee <jordan@example.test>",
        "subject": "[Demo] Project X planning meeting",
        "body": "Synthetic demo email. Please join Project X planning on 2026-09-03 at 10:00 AM.",
        "category": "meeting", "priority": "high", "reply_required": True, "tasks": [],
        "meeting": {"title": "Project X planning", "date": "2026-09-03", "time": "10:00", "participants": ["Jordan Lee"], "location_or_link": "Demo meeting room"},
    },
    {
        "id": "demo-deployment",
        "sender": "DevOps <devops@example.test>",
        "subject": "[Demo] Deployment review requested",
        "body": "Synthetic demo email. Priya requested a deployment review before the Friday release deadline.",
        "category": "action_required", "priority": "high", "reply_required": False,
        "tasks": [{"title": "Review deployment", "description": "Review release readiness", "normalized_deadline": "2026-09-04"}],
    },
    {
        "id": "demo-receipt",
        "sender": "Billing <billing@example.test>",
        "subject": "[Demo] August payment receipt",
        "body": "Synthetic demo email. Payment receipt for your records.",
        "category": "receipt", "priority": "low", "reply_required": False, "tasks": [],
    },
    {
        "id": "demo-newsletter",
        "sender": "Engineering Digest <digest@example.test>",
        "subject": "[Demo] Weekly engineering digest",
        "body": "Synthetic demo email. Weekly newsletter containing industry links.",
        "category": "newsletter", "priority": "low", "reply_required": False, "tasks": [],
    },
]


def analysis(item: dict) -> EmailAnalysis:
    return EmailAnalysis(
        sender=item["sender"], subject=item["subject"],
        summary=item["body"].replace("Synthetic demo email. ", ""),
        classification={"category": item["category"], "priority": item["priority"], "reason": "Synthetic demo classification."},
        tasks=item.get("tasks", []), meeting=item.get("meeting"),
        entities={"people": [], "organizations": [], "dates": [], "locations": []},
        reply_required=item["reply_required"],
    )


def main() -> None:
    created = cached = 0
    with get_session_factory()() as db:
        persistence = EmailPersistenceService(db)
        for item in DEMO_EMAILS:
            email = GmailEmail(
                message_id=item["id"], thread_id=f"thread-{item['id']}", sender=item["sender"],
                recipients=["demo.user@example.test"], subject=item["subject"], body=item["body"],
                received_at=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc), labels=["INBOX", "DEMO"],
            )
            result = persistence.save_analyzed_email(email, analysis(item))
            created += int(result.created)
            cached += int(not result.created)
    print(f"Synthetic demo data ready: {created} created, {cached} already present.")


if __name__ == "__main__":
    main()
