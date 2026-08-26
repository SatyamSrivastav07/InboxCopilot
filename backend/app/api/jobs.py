from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.jobs import JobState
from app.services.job_dependencies import get_job_service
from app.services.jobs import JobService

router = APIRouter(prefix="/api/jobs", tags=["background-jobs"])


@router.get("/{job_id}", response_model=JobState)
def get_job_status(
    job_id: str,
    jobs: Annotated[JobService, Depends(get_job_service)],
) -> JobState:
    return jobs.status(job_id)
