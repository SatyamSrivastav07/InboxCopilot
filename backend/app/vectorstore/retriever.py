from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Protocol

from app.schemas.search import SearchFilters, SemanticSearchResult
from app.vectorstore.errors import EmbeddingError
from app.vectorstore.store import ChromaStore

logger = logging.getLogger(__name__)


class QueryEmbeddings(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class RetrievedEmail:
    email_id: int
    gmail_thread_id: str
    subject: str
    sender: str
    received_at: str
    category: str
    priority: str
    score: float
    content: str

    def snippet(self, limit: int = 320) -> str:
        compact = re.sub(r"\s+", " ", self.content).strip()
        return compact if len(compact) <= limit else f"{compact[: limit - 1].rstrip()}…"

    def to_schema(self) -> SemanticSearchResult:
        return SemanticSearchResult(
            email_id=self.email_id,
            gmail_thread_id=self.gmail_thread_id,
            subject=self.subject,
            sender=self.sender,
            received_at=self.received_at or None,
            category=self.category,
            priority=self.priority,
            score=round(self.score, 4),
            snippet=self.snippet(),
        )


def _metadata_filter(
    filters: SearchFilters | None, *, user_id: int | None = None
) -> dict[str, Any] | None:
    clauses: list[dict[str, Any]] = []
    if filters and filters.sender:
        clauses.append({"sender": filters.sender})
    if filters and filters.category:
        clauses.append({"category": filters.category.value})
    if filters and filters.priority:
        clauses.append({"priority": filters.priority.value})
    if filters and filters.date_from:
        start = datetime.combine(filters.date_from, time.min, tzinfo=timezone.utc)
        clauses.append({"received_timestamp": {"$gte": start.timestamp()}})
    if filters and filters.date_to:
        end = datetime.combine(filters.date_to, time.max, tzinfo=timezone.utc)
        clauses.append({"received_timestamp": {"$lte": end.timestamp()}})
    if user_id is not None:
        clauses.append({"user_id": user_id})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class VectorRetriever:
    def __init__(self, store: ChromaStore, embeddings: QueryEmbeddings) -> None:
        self.store = store
        self.embeddings = embeddings

    def search(
        self,
        query: str,
        *,
        top_k: int,
        filters: SearchFilters | None = None,
        user_id: int | None = None,
    ) -> list[RetrievedEmail]:
        try:
            query_vector = self.embeddings.embed_query(query)
        except Exception as exc:
            raise EmbeddingError("Mistral could not embed the search query.") from exc

        raw = self.store.query(
            query_embedding=query_vector,
            top_k=max(top_k * 3, 10),
            where=_metadata_filter(filters, user_id=user_id),
        )
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        results: list[RetrievedEmail] = []
        seen_emails: set[int] = set()
        thread_counts: dict[str, int] = {}

        for document, metadata, distance in zip(documents, metadatas, distances):
            try:
                email_id = int(metadata["email_id"])
                thread_id = str(metadata["gmail_thread_id"])
                if email_id in seen_emails or thread_counts.get(thread_id, 0) >= 2:
                    continue
                result = RetrievedEmail(
                    email_id=email_id,
                    gmail_thread_id=thread_id,
                    subject=str(metadata["subject"]),
                    sender=str(metadata["sender"]),
                    received_at=str(metadata.get("received_at", "")),
                    category=str(metadata["category"]),
                    priority=str(metadata["priority"]),
                    score=max(0.0, min(1.0, 1.0 - float(distance))),
                    content=str(document),
                )
            except (KeyError, TypeError, ValueError):
                logger.warning("Skipping vector result with malformed metadata")
                continue
            seen_emails.add(email_id)
            thread_counts[thread_id] = thread_counts.get(thread_id, 0) + 1
            results.append(result)
            if len(results) >= top_k:
                break

        logger.info("Semantic query returned %s email results", len(results))
        return results
