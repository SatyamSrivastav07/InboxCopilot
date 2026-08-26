from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.runnables import RunnableLambda

from app.config import Settings
from app.genai.query_router import QueryRouter
from app.genai.rag import InboxRAG, NO_EVIDENCE_ANSWER
from app.genai.reply_chain import validate_reply_body
from app.schemas.query import QueryRouteType
from app.vectorstore.retriever import RetrievedEmail


CASES = json.loads((Path(__file__).parent / "evals" / "email_cases.json").read_text(encoding="utf-8"))


def settings(tmp_path: Path) -> Settings:
    return Settings(gmail_token_file=tmp_path / "token.json", chroma_persist_directory=tmp_path / "chroma")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_email_eval_fixture_has_safe_high_level_expectations(case):
    assert case["expected_category"]
    assert isinstance(case["expected_reply_required"], bool)
    assert case["expected_task_count_min"] >= 0
    assert isinstance(case["expected_meeting_presence"], bool)
    assert "@example.test" in case["sender"]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What tasks are pending?", QueryRouteType.STRUCTURED),
        ("What did HR say about onboarding?", QueryRouteType.SEMANTIC),
        ("What should I prioritize today?", QueryRouteType.HYBRID),
        ("What is the capital of France?", QueryRouteType.UNSUPPORTED),
    ],
)
def test_router_eval_fixture_routes_deterministically(tmp_path, question, expected):
    route_values = {
        "What tasks are pending?": "structured",
        "What did HR say about onboarding?": "semantic",
        "What should I prioritize today?": "structured",
        "What is the capital of France?": "unsupported",
    }
    router = QueryRouter(
        settings(tmp_path),
        route_chain=RunnableLambda(lambda _: {"route": route_values[question], "intent": "eval", "reason": "Offline eval", "confidence": 0.9}),
    )
    assert router.route(question).route == expected


class OnboardingRetriever:
    def search(self, query, *, top_k, filters=None):
        if "onboarding" not in query.lower():
            return []
        return [RetrievedEmail(email_id=42, gmail_thread_id="demo-thread", subject="Onboarding", sender="hr@example.test", received_at="2026-08-26T10:00:00+00:00", category="needs_reply", priority="high", score=0.95, content="HR requested onboarding documents.")]


def test_rag_eval_returns_grounded_source_and_rejects_unsupported_question(tmp_path):
    rag = InboxRAG(OnboardingRetriever(), settings(tmp_path), model=RunnableLambda(lambda _: "HR requested onboarding documents."))
    supported = rag.ask("What did HR say about onboarding?")
    unsupported = rag.ask("What is the capital of France?")
    assert supported.sources[0].email_id == 42
    assert "onboarding documents" in supported.answer.lower()
    assert unsupported.answer == NO_EVIDENCE_ANSWER
    assert unsupported.sources == []


@pytest.mark.parametrize(
    ("body", "instruction", "expected_safe"),
    [
        ("I can attend Monday.", None, False),
        ("I have attached the report.", None, False),
        ("Thank you. I will review this and get back to you.", None, True),
        ("I confirm I can attend Monday.", "Please confirm attendance", True),
    ],
)
def test_reply_safety_eval_blocks_unsupported_claims(body, instruction, expected_safe):
    assert validate_reply_body(body, instruction).safe is expected_safe
