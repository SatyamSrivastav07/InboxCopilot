from __future__ import annotations

import logging
from collections.abc import Callable

from app.config import ConfigurationError
from app.core.metrics import log_timing
from app.core.retry import call_with_retry
from app.database.errors import RecordNotFoundError
from app.database.errors import DatabaseServiceError
from app.genai.analyzer import EmailAnalyzer
from app.gmail.errors import (
    GmailAPIError,
    GmailNotConnectedError,
    GmailParseError,
    GmailRateLimitError,
)
from app.gmail.fetcher import GmailFetcher
from app.gmail.parser import parse_gmail_message
from app.gmail.schemas import GmailEmail, GmailSyncItem, GmailSyncRequest, GmailSyncResponse
from app.schemas.email import EmailInput
from app.services.email_persistence import EmailPersistenceService
from app.services.mappers import record_to_analysis, record_to_gmail
from app.vectorstore.errors import VectorStoreError
from app.vectorstore.indexer import VectorIndexer

logger = logging.getLogger(__name__)


class GmailSyncService:
    def __init__(
        self,
        fetcher: GmailFetcher,
        analyzer: EmailAnalyzer,
        persistence: EmailPersistenceService,
        indexer: VectorIndexer | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.analyzer = analyzer
        self.persistence = persistence
        self.indexer = indexer

    def sync(self, request: GmailSyncRequest) -> GmailSyncResponse:
        message_ids = self.fetcher.list_message_ids(
            limit=request.limit, unread_only=request.unread_only
        )
        results: list[GmailSyncItem] = []

        for message_id in message_ids:
            gmail_email: GmailEmail | None = None
            try:
                gmail_email = parse_gmail_message(self.fetcher.fetch_message(message_id))
                if not gmail_email.body.strip():
                    raise ValueError("Email body is empty; AI analysis was skipped.")

                cached = self.persistence.get_by_gmail_message_id(message_id)
                if cached:
                    if self.indexer:
                        self.indexer.index_email(cached)
                    results.append(
                        GmailSyncItem(
                            message_id=message_id,
                            source="cached",
                            gmail=record_to_gmail(cached),
                            analysis=record_to_analysis(cached),
                        )
                    )
                    continue

                analysis = self.analyzer.analyze(
                    EmailInput(
                        sender=gmail_email.sender or "Unknown sender",
                        subject=gmail_email.subject or "(No subject)",
                        body=gmail_email.body,
                    )
                )
                saved = self.persistence.save_analyzed_email(gmail_email, analysis)
                if self.indexer:
                    self.indexer.index_email(saved.email)
                results.append(
                    GmailSyncItem(
                        message_id=message_id,
                        source="processed" if saved.created else "cached",
                        gmail=record_to_gmail(saved.email),
                        analysis=record_to_analysis(saved.email),
                    )
                )
            except (
                GmailRateLimitError,
                GmailAPIError,
                GmailNotConnectedError,
                ConfigurationError,
                DatabaseServiceError,
                VectorStoreError,
            ):
                raise
            except Exception as exc:
                logger.warning(
                    "Gmail message %s could not be analyzed", message_id, exc_info=True
                )
                if isinstance(exc, GmailParseError):
                    error_message = "Email could not be parsed."
                elif isinstance(exc, ValueError) and "body is empty" in str(exc):
                    error_message = str(exc)
                else:
                    error_message = "Analysis failed."
                results.append(
                    GmailSyncItem(
                        message_id=message_id,
                        gmail=gmail_email,
                        error=error_message,
                    )
                )

        analyzed_count = sum(item.analysis is not None for item in results)
        return GmailSyncResponse(
            count=len(results),
            analyzed_count=analyzed_count,
            failed_count=len(results) - analyzed_count,
            emails=results,
        )

    def sync_background(
        self,
        request: GmailSyncRequest,
        *,
        progress_callback: Callable[[int, int, int, list[dict]], None] | None = None,
    ) -> dict[str, object]:
        with log_timing(logger, "gmail_fetch_list"):
            message_ids = call_with_retry(
                lambda: self.fetcher.list_message_ids(
                    limit=request.limit, unread_only=request.unread_only
                )
            )
        total = len(message_ids)
        processed = cached = failed = 0
        failed_items: list[dict] = []
        if progress_callback:
            progress_callback(total, 0, 0, [])

        for message_id in message_ids:
            record = None
            try:
                existing = self.persistence.get_by_gmail_message_id(message_id)
                if existing and existing.processing_status == "processed":
                    cached += 1
                    if self.indexer and existing.vector_status != "indexed":
                        self._index(existing)
                    continue

                with log_timing(logger, "gmail_fetch_message", gmail_message_id=message_id):
                    gmail_email = parse_gmail_message(
                        call_with_retry(lambda: self.fetcher.fetch_message(message_id))
                    )
                if not gmail_email.body.strip():
                    raise ValueError("Email body is empty; AI analysis was skipped.")
                reservation = self.persistence.create_pending_email(gmail_email)
                record = reservation.email
                if not reservation.created and record.processing_status == "processed":
                    cached += 1
                    if self.indexer and record.vector_status != "indexed":
                        self._index(record)
                    continue
                if not reservation.created and record.processing_status == "pending":
                    # Another worker won the unique Gmail ID race.
                    cached += 1
                    continue

                with log_timing(logger, "llm_email_analysis", email_id=record.id):
                    analysis = call_with_retry(
                        lambda: self.analyzer.analyze(
                            EmailInput(
                                sender=gmail_email.sender or "Unknown sender",
                                subject=gmail_email.subject or "(No subject)",
                                body=gmail_email.body,
                            )
                        )
                    )
                with log_timing(logger, "db_email_persistence", email_id=record.id):
                    record = self.persistence.complete_analysis(record, analysis)
                if self.indexer:
                    self._index(record)
                processed += 1
            except Exception as exc:
                failed += 1
                reason = self._safe_failure_reason(exc)
                if record is not None and record.processing_status != "processed":
                    try:
                        self.persistence.mark_processing_failed(record, reason)
                    except Exception:
                        logger.exception(
                            "event=email_failure_state_write_failed gmail_message_id=%s",
                            message_id,
                        )
                failed_items.append(
                    {
                        "email_id": getattr(record, "id", None),
                        "gmail_message_id": message_id,
                        "reason": reason,
                    }
                )
                logger.warning(
                    "event=gmail_email_processing_failed gmail_message_id=%s status=failed",
                    message_id,
                    exc_info=True,
                )
            finally:
                done = processed + cached + failed
                if progress_callback:
                    progress_callback(total, done, failed, failed_items)

        status = "partial_success" if failed and (processed or cached) else "failed" if failed else "completed"
        return {
            "status": status,
            "progress": {"total": total, "processed": total, "failed": failed},
            "result": {
                "total": total,
                "cached": cached,
                "processed": processed,
                "failed": failed,
            },
            "failed": failed_items,
        }

    def reprocess(self, email_id: int) -> dict[str, object]:
        record = self.persistence.get_by_id(email_id)
        if record is None:
            raise RecordNotFoundError("Persisted email was not found.")
        self.persistence.mark_reprocessing(record)
        try:
            analysis = call_with_retry(
                lambda: self.analyzer.analyze(
                    EmailInput(
                        sender=record.sender or "Unknown sender",
                        subject=record.subject or "(No subject)",
                        body=record.body_cleaned,
                    )
                )
            )
            record = self.persistence.complete_analysis(record, analysis)
            if self.indexer:
                self._index(record)
            return {
                "status": "completed",
                "progress": {"total": 1, "processed": 1, "failed": 0},
                "result": {"email_id": record.id, "processed": 1, "failed": 0},
                "failed": [],
            }
        except Exception as exc:
            reason = self._safe_failure_reason(exc)
            if record.processing_status != "processed":
                self.persistence.mark_processing_failed(record, reason)
            return {
                "status": "failed",
                "progress": {"total": 1, "processed": 1, "failed": 1},
                "result": {"email_id": record.id, "processed": 0, "failed": 1},
                "failed": [{"email_id": record.id, "reason": reason}],
            }

    def _index(self, record) -> None:
        try:
            with log_timing(logger, "vector_index", email_id=record.id):
                call_with_retry(lambda: self.indexer.index_email(record))
            self.persistence.mark_vector_status(record, "indexed")
        except Exception:
            self.persistence.mark_vector_status(record, "failed")
            raise

    @staticmethod
    def _safe_failure_reason(exc: Exception) -> str:
        if isinstance(exc, ValueError) and "body is empty" in str(exc):
            return "Email body is empty; analysis was skipped."
        if isinstance(exc, GmailParseError):
            return "Email could not be parsed."
        if isinstance(exc, GmailNotConnectedError):
            return "Gmail authorization is invalid or expired."
        if isinstance(exc, ConfigurationError):
            return "The AI provider is not configured."
        if isinstance(exc, GmailRateLimitError):
            return "Gmail rate limit persisted after retries."
        if isinstance(exc, VectorStoreError):
            return "Vector indexing failed after retries."
        return "Analysis failed after retries."
