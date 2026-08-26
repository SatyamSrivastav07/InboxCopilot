#!/bin/sh
set -eu

# Render exposes one public web process. Keep the Celery worker in this same
# container so it shares the persistent Chroma and single-user OAuth disk.
mkdir -p /app/data/chromadb /app/data/gmail
alembic upgrade head

celery -A app.workers.celery_app:celery_app worker --loglevel="${LOG_LEVEL:-info}" --concurrency="${CELERY_CONCURRENCY:-2}" &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
