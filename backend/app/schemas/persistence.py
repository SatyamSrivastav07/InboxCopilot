from __future__ import annotations

from datetime import date, datetime, time as time_type

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.email import Classification, EmailCategory, Priority


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceEmail(ORMResponse):
    id: int
    sender: str
    subject: str


class PersistedTask(ORMResponse):
    id: int
    email_id: int
    title: str
    description: str
    raw_deadline: str | None
    normalized_deadline: date | None
    priority: Priority
    completed: bool
    created_at: datetime
    updated_at: datetime
    source_email: SourceEmail | None = None


class PersistedMeeting(ORMResponse):
    id: int
    email_id: int
    title: str
    raw_date: str | None
    normalized_date: date | None
    time: time_type | None = Field(validation_alias="meeting_time")
    participants: list[str]
    location_or_link: str | None
    created_at: datetime
    updated_at: datetime
    source_email: SourceEmail | None = None


class PersistedEntity(ORMResponse):
    id: int
    email_id: int
    entity_type: str
    entity_value: str


class PersistedEmail(ORMResponse):
    id: int
    gmail_message_id: str
    gmail_thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    body_original: str
    body_cleaned: str
    received_at: datetime | None
    labels: list[str]
    summary: str
    classification: Classification
    reply_required: bool
    processing_status: str
    processing_error: str | None
    processing_attempts: int
    vector_status: str
    tasks: list[PersistedTask]
    meeting: PersistedMeeting | None
    entities: list[PersistedEntity]
    processed_at: datetime
    created_at: datetime
    updated_at: datetime


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: bool


class DashboardStats(BaseModel):
    total_emails: int
    needs_reply: int
    pending_tasks: int
    high_urgent: int
    upcoming_meetings: int
