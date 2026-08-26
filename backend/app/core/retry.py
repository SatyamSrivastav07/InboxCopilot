from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from app.config import ConfigurationError, get_settings
from app.gmail.errors import (
    GmailMessageNotFoundError,
    GmailNotConnectedError,
    GmailParseError,
    GmailRateLimitError,
)
from app.vectorstore.errors import VectorStoreError

T = TypeVar("T")


NON_RETRYABLE = (
    ConfigurationError,
    GmailMessageNotFoundError,
    GmailNotConnectedError,
    GmailParseError,
    ValueError,
)


def _retry_wait(retry_state) -> float:
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    retry_after = getattr(exception, "retry_after", None)
    if retry_after is not None:
        return min(max(float(retry_after), 0), 60)
    return wait_exponential_jitter(initial=2, max=8, jitter=1)(retry_state)


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, NON_RETRYABLE):
        return False
    if isinstance(exc, (GmailRateLimitError, VectorStoreError, TimeoutError, ConnectionError)):
        return True
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    return any(token in name or token in message for token in (
        "timeout", "ratelimit", "rate_limit", "temporar", "connection", "unavailable", "429", "502", "503", "504"
    ))


def call_with_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int | None = None,
    before_sleep: Callable[..., None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> T:
    attempts = max_attempts or get_settings().genai_max_retries
    retrying = Retrying(
        stop=stop_after_attempt(attempts),
        wait=_retry_wait,
        retry=retry_if_exception(is_transient_error),
        reraise=True,
        before_sleep=before_sleep,
        **({"sleep": sleep} if sleep is not None else {}),
    )
    return retrying(operation)
