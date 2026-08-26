class DatabaseServiceError(RuntimeError):
    """Base exception for safe database-facing API errors."""


class DatabaseUnavailableError(DatabaseServiceError):
    """Raised when PostgreSQL cannot be reached or is not migrated."""


class PersistenceError(DatabaseServiceError):
    """Raised when an analyzed email transaction cannot be committed."""


class RecordNotFoundError(DatabaseServiceError):
    """Raised when a requested persisted record does not exist."""

