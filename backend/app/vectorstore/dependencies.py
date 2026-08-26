from functools import lru_cache

from app.config import get_settings
from app.genai.rag import InboxRAG
from app.vectorstore.embeddings import build_embeddings
from app.vectorstore.indexer import VectorIndexer
from app.vectorstore.retriever import VectorRetriever
from app.vectorstore.store import ChromaStore


@lru_cache
def get_vector_store() -> ChromaStore:
    return ChromaStore(get_settings())


@lru_cache
def get_vector_embeddings():
    return build_embeddings(get_settings())


@lru_cache
def get_vector_indexer() -> VectorIndexer:
    return VectorIndexer(get_vector_store(), get_vector_embeddings(), get_settings())


@lru_cache
def get_vector_retriever() -> VectorRetriever:
    return VectorRetriever(get_vector_store(), get_vector_embeddings())


@lru_cache
def get_inbox_rag() -> InboxRAG:
    return InboxRAG(get_vector_retriever(), get_settings())
