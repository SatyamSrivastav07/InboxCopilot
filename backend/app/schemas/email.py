from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailCategory(str, Enum):
    ACTION_REQUIRED = "action_required"
    NEEDS_REPLY = "needs_reply"
    MEETING = "meeting"
    IMPORTANT_UPDATE = "important_update"
    NEWSLETTER = "newsletter"
    PROMOTION = "promotion"
    RECEIPT = "receipt"
    NOTIFICATION = "notification"
    LOW_VALUE = "low_value"
    OTHER = "other"


class Priority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmailInput(StrictModel):
    sender: str = Field(min_length=1, max_length=320)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=100_000)


class Classification(StrictModel):
    category: EmailCategory
    priority: Priority
    reason: str = Field(min_length=1)


class Task(StrictModel):
    title: str = Field(min_length=1)
    description: str
    raw_deadline: str | None = None
    normalized_deadline: str | None = Field(
        default=None,
        description="ISO date (YYYY-MM-DD), or null when the date cannot be resolved safely.",
    )


class Meeting(StrictModel):
    title: str = Field(min_length=1)
    date: str | None = None
    time: str | None = None
    participants: list[str] = Field(default_factory=list)
    location_or_link: str | None = None


class Entities(StrictModel):
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)


class EmailAnalysis(StrictModel):
    sender: str
    subject: str
    summary: str
    classification: Classification
    tasks: list[Task]
    meeting: Meeting | None
    entities: Entities
    reply_required: bool


# Internal structured-output schemas used by individual parallel branches.
class ClassificationResult(StrictModel):
    category: EmailCategory
    priority: Priority
    reason: str
    reply_required: bool


class SummaryResult(StrictModel):
    summary: str = Field(min_length=1)


class TaskExtractionResult(StrictModel):
    tasks: list[Task] = Field(default_factory=list)


class MeetingExtractionResult(StrictModel):
    meeting: Meeting | None = None

