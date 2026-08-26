from __future__ import annotations

from datetime import date as date_type
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.email import EmailCategory, Priority
from app.schemas.draft import ReplyDraft
from app.schemas.search import InboxSource, SearchFilters


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryRouteType(str, Enum):
    STRUCTURED = "structured"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    UNSUPPORTED = "unsupported"
    REPLY_DRAFT = "reply_draft"


class StructuredIntent(str, Enum):
    LIST_TASKS = "list_tasks"
    COUNT_TASKS = "count_tasks"
    LIST_DEADLINES = "list_deadlines"
    LIST_MEETINGS = "list_meetings"
    COUNT_EMAILS = "count_emails"
    LIST_EMAILS = "list_emails"
    NEEDS_REPLY = "needs_reply"
    PRIORITY_SUMMARY = "priority_summary"


class QueryRoute(QueryModel):
    route: QueryRouteType
    intent: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class StructuredQuery(QueryModel):
    intent: StructuredIntent
    completed: bool | None = None
    priority: Priority | None = None
    category: EmailCategory | None = None
    reply_required: bool | None = None
    date_from: date_type | None = None
    date_to: date_type | None = None
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self


class StructuredItem(QueryModel):
    kind: str
    title: str
    description: str | None = None
    date: date_type | None = None
    time: str | None = None
    priority: str | None = None
    completed: bool | None = None
    email_id: int | None = None
    subject: str | None = None
    sender: str | None = None


class StructuredQueryResult(QueryModel):
    intent: StructuredIntent
    count: int | None = None
    items: list[StructuredItem] = Field(default_factory=list)
    priority_counts: dict[str, int] = Field(default_factory=dict)


class RoutedInboxRequest(QueryModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=10)
    filters: SearchFilters | None = None


class RoutedInboxResponse(QueryModel):
    answer: str
    sources: list[InboxSource] = Field(default_factory=list)
    route: QueryRouteType
    intent: str
    reason: str
    confidence: float
    draft: ReplyDraft | None = None
