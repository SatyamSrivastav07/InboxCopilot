from __future__ import annotations

from app.database.session import get_session_factory
from app.services.reindex import ReindexService
from app.vectorstore.dependencies import get_vector_indexer
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="app.workers.indexing_tasks.reindex_inbox")
def reindex_inbox(self, user_id: int | None = None) -> dict[str, object]:
    def progress(total: int, processed: int, failed: int, failed_items: list[dict]) -> None:
        self.update_state(
            state="STARTED",
            meta={"progress": {"total": total, "processed": processed, "failed": failed}, "failed": failed_items},
        )

    with get_session_factory()() as db:
        result = ReindexService(db, get_vector_indexer(), user_id).reindex_background(progress)
    return result
