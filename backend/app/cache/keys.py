DASHBOARD_KEY = "cache:dashboard:v2"
LEGACY_DASHBOARD_KEYS = ("cache:dashboard:v1",)
SYNC_LOCK_KEY = "lock:gmail-sync:local-account"


def job_lock_key(name: str) -> str:
    return f"lock:job:{name}"


def dashboard_key(user_id: int) -> str:
    """Per-user cache namespace for authenticated dashboard requests."""
    return f"cache:dashboard:v3:user:{user_id}"


def gmail_sync_lock_key(user_id: int) -> str:
    """Prevent duplicate Gmail syncs for one account without blocking others."""
    return f"lock:gmail-sync:user:{user_id}"


def inbox_reindex_lock_key(user_id: int) -> str:
    return f"lock:inbox-reindex:user:{user_id}"


def email_reprocess_lock_key(user_id: int, email_id: int) -> str:
    return f"lock:email-reprocess:user:{user_id}:email:{email_id}"
