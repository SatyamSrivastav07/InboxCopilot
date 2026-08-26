from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.email import EmailAnalysis


class GmailModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GmailEmail(GmailModel):
    message_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    sender: str
    recipients: list[str] = Field(default_factory=list)
    subject: str
    body: str
    received_at: datetime | str
    labels: list[str] = Field(default_factory=list)
    reply_to: str | None = None
    internet_message_id: str | None = None
    references: list[str] = Field(default_factory=list)


class GmailStatus(GmailModel):
    connected: bool
    can_read: bool
    can_send: bool


class GmailAuthUrl(GmailModel):
    authorization_url: str


class GmailSyncRequest(GmailModel):
    limit: Literal[5, 10, 20] = 10
    unread_only: bool = False


class GmailSyncItem(GmailModel):
    message_id: str
    source: Literal["cached", "processed"] | None = None
    gmail: GmailEmail | None = None
    analysis: EmailAnalysis | None = None
    error: str | None = None

    @model_validator(mode="after")
    def has_result_or_error(self) -> "GmailSyncItem":
        if self.analysis is None and self.error is None:
            raise ValueError("A sync item must contain an analysis or an error")
        return self


class GmailSyncResponse(GmailModel):
    count: int
    analyzed_count: int
    failed_count: int
    emails: list[GmailSyncItem]
