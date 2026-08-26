from fastapi.testclient import TestClient

from app.main import app
from app.schemas.query import RoutedInboxResponse
from app.schemas.search import InboxSource, ReindexResponse
from app.services.dependencies import get_inbox_query_workflow, get_reindex_service
from app.vectorstore.dependencies import get_vector_retriever
from app.vectorstore.retriever import RetrievedEmail


def retrieved():
    return RetrievedEmail(
        email_id=3,
        gmail_thread_id="thread-3",
        subject="Deployment schedule",
        sender="release@example.com",
        received_at="2026-08-20T10:00:00+00:00",
        category="action_required",
        priority="high",
        score=0.94,
        content="Production deployment is scheduled for Friday.",
    )


class StubRetriever:
    def search(self, query, *, top_k, filters=None):
        assert query == "production release"
        assert top_k == 4
        return [retrieved()]


class StubWorkflow:
    def ask(self, question, *, top_k=None, filters=None):
        assert question == "When is production deployment?"
        return RoutedInboxResponse(
            answer="Production deployment is scheduled for Friday.",
            sources=[
                InboxSource(
                    email_id=3,
                    subject="Deployment schedule",
                    sender="release@example.com",
                    received_at="2026-08-20T10:00:00+00:00",
                    snippet="Production deployment is scheduled for Friday.",
                )
            ],
            route="semantic",
            intent="deployment_discussion",
            reason="The question asks what an email discussed.",
            confidence=0.96,
        )


class StubReindexService:
    def reindex_all(self):
        return ReindexResponse(emails_indexed=2, emails_skipped=0, chunks_created=5)


def test_semantic_search_api_returns_citable_email():
    app.dependency_overrides[get_vector_retriever] = lambda: StubRetriever()
    try:
        response = TestClient(app).post(
            "/api/search/semantic",
            json={"query": "production release", "top_k": 4},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["results"][0]["email_id"] == 3
    assert response.json()["results"][0]["score"] == 0.94


def test_inbox_chat_api_returns_answer_and_sources():
    app.dependency_overrides[get_inbox_query_workflow] = lambda: StubWorkflow()
    try:
        response = TestClient(app).post(
            "/api/chat/inbox", json={"question": "When is production deployment?"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["answer"].endswith("Friday.")
    assert response.json()["sources"][0]["email_id"] == 3
    assert response.json()["route"] == "semantic"


def test_reindex_api_reports_rebuilt_collection():
    app.dependency_overrides[get_reindex_service] = lambda: StubReindexService()
    try:
        response = TestClient(app).post("/api/search/reindex")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "emails_indexed": 2,
        "emails_skipped": 0,
        "chunks_created": 5,
    }
