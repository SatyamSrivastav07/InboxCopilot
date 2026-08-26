from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from collections.abc import Iterator


@contextmanager
def log_timing(logger: logging.Logger, event: str, **fields: object) -> Iterator[None]:
    started = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "failed"
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000)
        rendered = " ".join(f"{key}={value}" for key, value in fields.items())
        logger.info("event=%s duration_ms=%s status=%s %s", event, duration_ms, status, rendered)
