class VectorStoreError(RuntimeError):
    """Raised when indexing or semantic retrieval cannot be completed."""


class EmbeddingError(VectorStoreError):
    """Raised when Mistral embeddings fail."""


class RetrievalError(VectorStoreError):
    """Raised when Chroma retrieval fails."""

