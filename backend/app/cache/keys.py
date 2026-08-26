DASHBOARD_KEY = "cache:dashboard:v1"
SYNC_LOCK_KEY = "lock:gmail-sync:local-account"


def job_lock_key(name: str) -> str:
    return f"lock:job:{name}"
