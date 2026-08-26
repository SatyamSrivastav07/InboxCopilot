#!/bin/sh
set -eu

# Render Free has no always-on worker or persistent disk. Database migrations
# still run before the API accepts traffic; user-requested sync runs inline.
mkdir -p /tmp/chromadb
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
