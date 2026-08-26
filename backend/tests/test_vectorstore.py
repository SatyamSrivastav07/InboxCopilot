from datetime import datetime, timezone

import chromadb

from app.config import Settings
from app.database.models.email import EmailRecord
from app.genai.rag import NO_EVIDENCE_ANSWER, InboxRAG, format_context, format_sources
from app.services.reindex import ReindexService
from app.vectorstore.indexer import IndexResult, VectorIndexer, vector_id
from app.vectorstore.retriever import RetrievedEmail, VectorRetriever
from app.vectorstore.store import ChromaStore


class KeywordEmbeddings:
    @staticmethod
    def _vector(text: str) -> list[float]:
        lower = text.lower()
        if "deployment" in lower or "release" in lower:
            return [1.0, 0.0, 0.0]
        if "onboarding" in lower or "welcome" in lower:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def settings(tmp_path, *, chunk_size=1000, chunk_overlap=100) -> Settings:
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
        chroma_persist_directory=tmp_path / "chroma",
        chroma_collection_name=f"test-{tmp_path.name}",
        email_chunk_size=chunk_size,
        email_chunk_overlap=chunk_overlap,
    )


def email(
    email_id: int,
    subject: str,
    body: str,
    *,
    thread_id: str | None = None,
    user_id: int = 1,
):
    return EmailRecord(
        id=email_id,
        user_id=user_id,
        gmail_message_id=f"gmail-{email_id}",
        gmail_thread_id=thread_id or f"thread-{email_id}",
        sender="sender@example.com",
        recipients=["user@example.com"],
        subject=subject,
        body_original=body,
        body_cleaned=body,
        received_at=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        labels=["INBOX"],
        category="action_required",
        priority="high",
        classification_reason="Action is requested.",
        summary=f"Summary: {subject}",
        reply_required=True,
    )


def vector_components(tmp_path, *, chunk_size=1000, chunk_overlap=100):
    config = settings(tmp_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    store = ChromaStore(config, client=chromadb.EphemeralClient())
    embeddings = KeywordEmbeddings()
    return config, store, embeddings, VectorIndexer(store, embeddings, config)


def test_email_is_chunked_with_metadata_and_deterministic_ids(tmp_path):
    _, store, _, indexer = vector_components(tmp_path, chunk_size=140, chunk_overlap=20)
    record = email(7, "Deployment release", "deployment checklist " * 30)

    result = indexer.index_email(record)
    stored = store.get_email_chunks(record.id)

    assert result.chunks_created > 1
    assert stored["ids"] == [
        vector_id(7, index, user_id=1) for index in range(result.chunks_created)
    ]
    assert all(metadata["email_id"] == 7 for metadata in stored["metadatas"])
    assert all(metadata["user_id"] == 1 for metadata in stored["metadatas"])
    assert all(metadata["gmail_thread_id"] == "thread-7" for metadata in stored["metadatas"])
    assert all(metadata["category"] == "action_required" for metadata in stored["metadatas"])


def test_duplicate_indexing_is_skipped(tmp_path):
    _, store, _, indexer = vector_components(tmp_path)
    record = email(2, "Onboarding", "Welcome to the onboarding plan.")

    first = indexer.index_email(record)
    second = indexer.index_email(record)

    assert first.skipped is False
    assert second.skipped is True
    assert len(store.get_email_chunks(2)["ids"]) == first.chunks_created


def test_semantic_retrieval_returns_best_email_and_deduplicates_chunks(tmp_path):
    _, store, embeddings, indexer = vector_components(tmp_path, chunk_size=120, chunk_overlap=10)
    indexer.index_email(email(1, "Deployment release", "deployment release status " * 20))
    indexer.index_email(email(2, "Welcome", "onboarding welcome guide " * 20))

    results = VectorRetriever(store, embeddings).search("deployment status", top_k=5)

    assert results[0].email_id == 1
    assert len([item for item in results if item.email_id == 1]) == 1
    assert results[0].score > results[-1].score


def test_semantic_retrieval_never_crosses_user_vector_namespace(tmp_path):
    _, store, embeddings, indexer = vector_components(tmp_path)
    indexer.index_email(email(1, "Owner deployment", "deployment release", user_id=1))
    indexer.index_email(email(1, "Other deployment", "deployment release", user_id=2))

    results = VectorRetriever(store, embeddings).search(
        "deployment release", top_k=5, user_id=1
    )

    assert [item.subject for item in results] == ["Owner deployment"]


def test_context_and_sources_preserve_email_citations():
    result = RetrievedEmail(
        email_id=4,
        gmail_thread_id="thread-4",
        subject="Contract update",
        sender="legal@example.com",
        received_at="2026-08-20T10:00:00+00:00",
        category="important_update",
        priority="high",
        score=0.91,
        content="The renewal date is September 1.",
    )

    context = format_context([result])
    sources = format_sources([result])

    assert "[Source 1]" in context
    assert "Email ID: 4" in context
    assert sources[0].email_id == 4
    assert sources[0].subject == "Contract update"


class EmptyRetriever:
    def search(self, query, *, top_k, filters=None):
        return []


def test_rag_returns_safe_answer_without_calling_model_when_no_results(tmp_path):
    rag = InboxRAG(EmptyRetriever(), settings(tmp_path))

    response = rag.ask("What did legal say?")

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.sources == []
    assert rag.model is None


class RecordingStore:
    def __init__(self):
        self.deleted_users = []

    def delete_user(self, user_id):
        self.deleted_users.append(user_id)


class RecordingIndexer:
    def __init__(self):
        self.store = RecordingStore()
        self.email_ids = []

    def reindex_email(self, record):
        self.email_ids.append(record.id)
        return IndexResult(record.id, chunks_created=2, skipped=False)


def test_reindex_rebuilds_vectors_for_every_persisted_email(db_session):
    db_session.add_all([
        email(11, "Deployment", "deployment plan"),
        email(12, "Onboarding", "onboarding guide"),
    ])
    db_session.commit()
    indexer = RecordingIndexer()

    response = ReindexService(db_session, indexer).reindex_all()

    assert indexer.store.deleted_users == [1]
    assert indexer.email_ids == [11, 12]
    assert response.emails_indexed == 2
    assert response.chunks_created == 4
