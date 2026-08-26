from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import chromadb
from chromadb.errors import NotFoundError
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.config import Settings
from app.vectorstore.errors import RetrievalError, VectorStoreError


class ChromaStore:
    """Small adapter that keeps Chroma details outside indexing/retrieval logic."""

    def __init__(
        self,
        settings: Settings,
        client: ClientAPI | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or chromadb.PersistentClient(
            path=str(settings.chroma_persist_directory)
        )
        self.collection_name = collection_name or settings.chroma_collection_name

    @property
    def collection(self) -> Collection:
        try:
            return self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorStoreError("The Chroma collection is unavailable.") from exc

    def get_email_chunks(self, email_id: int) -> dict[str, Any]:
        try:
            return self.collection.get(
                where={"email_id": email_id}, include=["metadatas"]
            )
        except Exception as exc:
            raise VectorStoreError("Could not inspect the email vector index.") from exc

    def upsert(
        self,
        *,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        try:
            self.collection.upsert(
                ids=list(ids),
                documents=list(documents),
                metadatas=list(metadatas),
                embeddings=[list(value) for value in embeddings],
            )
        except Exception as exc:
            raise VectorStoreError("Could not update the email vector index.") from exc

    def delete_email(self, email_id: int) -> None:
        try:
            self.collection.delete(where={"email_id": email_id})
        except Exception as exc:
            raise VectorStoreError("Could not delete email vectors.") from exc

    def clear(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except NotFoundError:
            # Rebuilding an absent collection is a valid operation.
            pass
        except Exception as exc:
            raise VectorStoreError("Could not clear the email vector index.") from exc

    def query(
        self,
        *,
        query_embedding: Sequence[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return self.collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise RetrievalError("Semantic inbox retrieval failed.") from exc
