class GmailError(RuntimeError):
    """Base exception for Gmail integration failures."""


class GmailNotConnectedError(GmailError):
    """Raised when an operation requires an OAuth connection."""


class GmailOAuthError(GmailError):
    """Raised when the OAuth flow cannot be completed safely."""


class GmailAPIError(GmailError):
    """Raised when Gmail cannot fulfill a request."""


class GmailRateLimitError(GmailAPIError):
    """Raised when Gmail rejects a request because of quota or rate limits."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GmailMessageNotFoundError(GmailAPIError):
    """Raised when a Gmail message was deleted or is no longer accessible."""


class GmailParseError(GmailError):
    """Raised when a Gmail payload cannot be normalized."""
