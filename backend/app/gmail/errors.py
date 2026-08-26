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


class GmailParseError(GmailError):
    """Raised when a Gmail payload cannot be normalized."""

