from datetime import date, datetime, timezone

from langchain_core.runnables import RunnableLambda

from app.config import Settings
from app.database.models.email import EmailRecord
from app.database.models.task import TaskRecord
from app.genai.inbox_workflow import InboxQueryWorkflow, UNSUPPORTED_ANSWER
from app.genai.query_router import QueryRouter
from app.schemas.query import (
    QueryRoute,
    QueryRouteType,
    StructuredIntent,
    StructuredQuery,
    StructuredQueryResult,
)
from app.schemas.search import AskInboxResponse, InboxSource
from app.services.structured_query_service import StructuredQueryService
from app.vectorstore.retriever import RetrievedEmail


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
    )


def test_query_router_validates_route_and_structured_parameters(tmp_path):
    router = QueryRouter(
        make_settings(tmp_path),
        route_chain=RunnableLambda(
            lambda _: {
                "route": "structured",
                "intent": "list_deadlines",
                "reason": "Deadlines are structured task fields.",
                "confidence": 0.93,
            }
        ),
        structured_chain=RunnableLambda(
            lambda _: {
                "intent": "list_deadlines",
                "completed": False,
                "date_from": "2026-08-26",
                "date_to": "2026-08-30",
                "limit": 20,
            }
        ),
    )

    route = router.route("What deadlines do I have this week?")
    query = router.structured_query("What deadlines do I have this week?", route)

    assert route.route == QueryRouteType.STRUCTURED
    assert route.confidence == 0.93
    assert query.intent == StructuredIntent.LIST_DEADLINES
    assert query.completed is False
    assert query.date_from == date(2026, 8, 26)


class FakeRouter:
    def __init__(self, route_type):
        self.route_type = route_type

    def route(self, question):
        return QueryRoute(
            route=self.route_type,
            intent=f"{self.route_type.value}_intent",
            reason="Test route",
            confidence=0.9,
        )

    def structured_query(self, question, route):
        return StructuredQuery(intent="priority_summary", limit=10)


class FakeStructuredService:
    def __init__(self):
        self.calls = 0

    def execute(self, query):
        self.calls += 1
        return StructuredQueryResult(
            intent=query.intent,
            count=2,
            priority_counts={"urgent": 1, "high": 1},
        )


class FakeRAG:
    def __init__(self):
        self.ask_calls = 0
        self.retrieve_calls = 0

    def ask(self, question, *, top_k=None, filters=None):
        self.ask_calls += 1
        return AskInboxResponse(
            answer="HR requested onboarding documents.",
            sources=[
                InboxSource(
                    email_id=8,
                    subject="Onboarding",
                    sender="hr@example.com",
                    received_at=None,
                    snippet="Please send the documents.",
                )
            ],
        )

    def retrieve(self, question, *, top_k=None, filters=None):
        self.retrieve_calls += 1
        return [
            RetrievedEmail(
                email_id=8,
                gmail_thread_id="thread-8",
                subject="Onboarding",
                sender="hr@example.com",
                received_at="2026-08-26T10:00:00+00:00",
                category="action_required",
                priority="urgent",
                score=0.9,
                content="Please send the onboarding documents today.",
            )
        ]


def workflow(tmp_path, route_type):
    structured = FakeStructuredService()
    rag = FakeRAG()
    result = InboxQueryWorkflow(
        FakeRouter(route_type),
        structured,
        rag,
        make_settings(tmp_path),
        hybrid_answer_chain=RunnableLambda(lambda _: "Handle the urgent onboarding request."),
    )
    return result, structured, rag


def test_runnable_branch_uses_structured_path_without_rag(tmp_path):
    flow, structured, rag = workflow(tmp_path, QueryRouteType.STRUCTURED)

    response = flow.ask("How many urgent emails do I have?")

    assert response.route == QueryRouteType.STRUCTURED
    assert "urgent: 1" in response.answer
    assert structured.calls == 1
    assert rag.ask_calls == 0
    assert rag.retrieve_calls == 0


def test_runnable_branch_reuses_semantic_rag_path(tmp_path):
    flow, structured, rag = workflow(tmp_path, QueryRouteType.SEMANTIC)

    response = flow.ask("What did HR say about onboarding?")

    assert response.answer == "HR requested onboarding documents."
    assert response.sources[0].email_id == 8
    assert rag.ask_calls == 1
    assert structured.calls == 0


def test_hybrid_branch_runs_structured_and_semantic_in_parallel(tmp_path):
    flow, structured, rag = workflow(tmp_path, QueryRouteType.HYBRID)

    response = flow.ask("What should I prioritize today?")

    assert response.route == QueryRouteType.HYBRID
    assert response.answer == "Handle the urgent onboarding request."
    assert response.sources[0].email_id == 8
    assert structured.calls == 1
    assert rag.retrieve_calls == 1


def test_unsupported_branch_does_not_query_data_sources(tmp_path):
    flow, structured, rag = workflow(tmp_path, QueryRouteType.UNSUPPORTED)

    response = flow.ask("Send a reply for me")

    assert response.answer == UNSUPPORTED_ANSWER
    assert response.sources == []
    assert structured.calls == 0
    assert rag.ask_calls == 0
    assert rag.retrieve_calls == 0


def persisted_email(email_id: int, *, reply_required=True, priority="high"):
    record = EmailRecord(
        id=email_id,
        gmail_message_id=f"gmail-{email_id}",
        gmail_thread_id=f"thread-{email_id}",
        sender="manager@example.com",
        recipients=["user@example.com"],
        subject="Release work",
        body_original="Finish the release checklist.",
        body_cleaned="Finish the release checklist.",
        received_at=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        category="action_required",
        priority=priority,
        classification_reason="Action required.",
        summary="Release work is required.",
        reply_required=reply_required,
    )
    record.tasks = [
        TaskRecord(
            title="Finish release checklist",
            description="Complete deployment checks.",
            raw_deadline="2026-08-27",
            normalized_deadline=date(2026, 8, 27),
            priority=priority,
            completed=False,
        )
    ]
    return record


def test_structured_service_executes_allow_listed_database_queries(db_session):
    db_session.add_all([
        persisted_email(21, reply_required=True, priority="urgent"),
        persisted_email(22, reply_required=False, priority="low"),
    ])
    db_session.commit()
    service = StructuredQueryService(db_session)

    replies = service.execute(StructuredQuery(intent="needs_reply"))
    deadlines = service.execute(
        StructuredQuery(
            intent="list_deadlines",
            completed=False,
            date_from=date(2026, 8, 27),
            date_to=date(2026, 8, 27),
        )
    )

    assert replies.count == 1
    assert replies.items[0].email_id == 21
    assert deadlines.count == 2
    assert all(item.kind == "task" for item in deadlines.items)
