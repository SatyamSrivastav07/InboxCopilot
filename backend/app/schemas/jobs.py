from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["queued", "running", "completed", "partial_success", "failed"]


class JobModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobQueued(JobModel):
    job_id: str
    status: Literal["queued"] = "queued"
    reused: bool = False


class JobProgress(JobModel):
    total: int = 0
    processed: int = 0
    failed: int = 0


class FailedJobItem(JobModel):
    email_id: int | None = None
    gmail_message_id: str | None = None
    reason: str


class JobState(JobModel):
    job_id: str
    status: JobStatus
    progress: JobProgress = Field(default_factory=JobProgress)
    result: dict[str, Any] | None = None
    failed: list[FailedJobItem] = Field(default_factory=list)
    error: str | None = None
