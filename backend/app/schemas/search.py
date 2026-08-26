from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.email import EmailCategory, Priority


class SearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchFilters(SearchModel):
    sender: str | None = None
    category: EmailCategory | None = None
    priority: Priority | None = None
    date_from: date | None = None
    date_to: date | None = None


class SemanticSearchRequest(SearchModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    filters: SearchFilters | None = None


class SemanticSearchResult(SearchModel):
    email_id: int
    gmail_thread_id: str
    subject: str
    sender: str
    received_at: datetime | str | None
    category: str
    priority: str
    score: float
    snippet: str


class SemanticSearchResponse(SearchModel):
    results: list[SemanticSearchResult]


class AskInboxRequest(SearchModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=10)
    filters: SearchFilters | None = None


class InboxSource(SearchModel):
    email_id: int
    subject: str
    sender: str
    received_at: datetime | str | None
    snippet: str


class AskInboxResponse(SearchModel):
    answer: str
    sources: list[InboxSource]


class ReindexResponse(SearchModel):
    emails_indexed: int
    emails_skipped: int
    chunks_created: int
