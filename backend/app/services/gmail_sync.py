from __future__ import annotations

import logging

from app.config import ConfigurationError
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
