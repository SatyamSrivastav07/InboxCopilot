from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.email import Priority
from app.schemas.persistence import PersistedTask, TaskUpdate
from app.services.dependencies import get_inbox_query_service
from app.services.inbox_queries import InboxQueryService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[PersistedTask])
def list_tasks(
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
    completed: bool | None = Query(default=None),
    priority: Priority | None = Query(default=None),
    deadline_from: date | None = Query(default=None),
    deadline_to: date | None = Query(default=None),
) -> list[PersistedTask]:
    if deadline_from and deadline_to and deadline_from > deadline_to:
        raise HTTPException(status_code=422, detail="deadline_from must not exceed deadline_to.")
    return service.list_tasks(
        completed=completed,
        priority=priority.value if priority else None,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
    )


@router.patch("/{task_id}", response_model=PersistedTask)
def update_task(
    task_id: int,
    update: TaskUpdate,
    service: Annotated[InboxQueryService, Depends(get_inbox_query_service)],
) -> PersistedTask:
    return service.update_task(task_id, update.completed)

