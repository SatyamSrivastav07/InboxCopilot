from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReplyTone(str, Enum):
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    FRIENDLY = "friendly"
    FORMAL = "formal"


class ReplyDraftRequest(DraftModel):
    instruction: str | None = Field(default=None, max_length=2000)
    tone: ReplyTone = ReplyTone.PROFESSIONAL


class ReplyDraftContent(DraftModel):
    body: str = Field(min_length=1, max_length=100_000)
    notes: list[str] = Field(default_factory=list)


class DraftValidation(DraftModel):
    safe: bool
    issues: list[str] = Field(default_factory=list)


class ReplyDraft(DraftModel):
    draft_id: int
    email_id: int
    recipient: str
    subject: str
    body: str
    generated_body: str
    status: Literal["draft", "approved", "sent", "failed"]
    notes: list[str] = Field(default_factory=list)
    attachment_warning: bool = False
    thread_message_count: int | None = None
    requires_user_confirmation: Literal[True] = True
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None
    sent_gmail_message_id: str | None = None


class DraftUpdate(DraftModel):
    body: str = Field(min_length=1, max_length=100_000)


class DraftSendResponse(DraftModel):
    draft_id: int
    status: Literal["sent"]
    gmail_message_id: str | None = None
    sent_at: datetime
