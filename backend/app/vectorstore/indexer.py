from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Settings
from app.database.models.email import EmailRecord
from app.vectorstore.errors import EmbeddingError
from app.vectorstore.store import ChromaStore

logger = logging.getLogger(__name__)


class DocumentEmbeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class IndexResult:
    email_id: int
    chunks_created: int
    skipped: bool


def retrieval_text(email: EmailRecord) -> str:
    received = email.received_at.isoformat() if email.received_at else "Unknown"
    return (
        f"Subject: {email.subject}\n"
        f"Sender: {email.sender}\n"
        f"Received At: {received}\n\n"
        f"Body:\n{email.body_cleaned}\n\n"
        f"AI Summary:\n{email.summary}"
    ).strip()


def vector_id(email_id: int, chunk_number: int) -> str:
    return f"email_{email_id}_chunk_{chunk_number}"


class VectorIndexer:
    def __init__(
        self,
        store: ChromaStore,
        embeddings: DocumentEmbeddings,
        settings: Settings,
    ) -> None:
        self.store = store
        self.embeddings = embeddings
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.email_chunk_size,
            chunk_overlap=settings.email_chunk_overlap,
        )

    def chunks_for_email(
        self, email: EmailRecord
    ) -> tuple[list[str], list[str], list[dict[str, Any]]]:
        text = retrieval_text(email)
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunks = self.splitter.split_text(text) or [text]
        received = email.received_at.isoformat() if email.received_at else ""
        received_timestamp = email.received_at.timestamp() if email.received_at else 0.0
        base_metadata: dict[str, Any] = {
            "email_id": email.id,
            "gmail_message_id": email.gmail_message_id,
            "gmail_thread_id": email.gmail_thread_id,
            "sender": email.sender,
            "subject": email.subject,
            "received_at": received,
            "received_timestamp": received_timestamp,
            "category": email.category,
            "priority": email.priority,
            "content_hash": content_hash,
        }
        ids = [vector_id(email.id, index) for index in range(len(chunks))]
        metadatas = [
            {**base_metadata, "chunk_number": index}
            for index in range(len(chunks))
        ]
        return ids, chunks, metadatas

    def index_email(self, email: EmailRecord, *, force: bool = False) -> IndexResult:
        ids, chunks, metadatas = self.chunks_for_email(email)
        content_hash = metadatas[0]["content_hash"]
        existing = self.store.get_email_chunks(email.id)
        existing_metadata = existing.get("metadatas") or []
        if (
            not force
            and existing_metadata
            and all(item.get("content_hash") == content_hash for item in existing_metadata)
            and len(existing_metadata) == len(chunks)
        ):
            logger.info("Email %s already indexed; skipping", email.id)
            return IndexResult(email_id=email.id, chunks_created=0, skipped=True)

        if existing.get("ids"):
            self.store.delete_email(email.id)
        try:
            vectors = self.embeddings.embed_documents(chunks)
        except Exception as exc:
            raise EmbeddingError("Mistral could not embed the email.") from exc
        self.store.upsert(
            ids=ids, documents=chunks, metadatas=metadatas, embeddings=vectors
        )
        logger.info("Indexed email %s into %s chunks", email.id, len(chunks))
        return IndexResult(email_id=email.id, chunks_created=len(chunks), skipped=False)

    def reindex_email(self, email: EmailRecord) -> IndexResult:
        return self.index_email(email, force=True)

    def delete_email_vectors(self, email_id: int) -> None:
        self.store.delete_email(email_id)

