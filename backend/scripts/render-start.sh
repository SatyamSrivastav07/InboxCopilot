#!/bin/sh
set -eu

# Render exposes one public web process. Keep the Celery worker in this same
# container so it shares the persistent Chroma disk. User OAuth credentials
# are encrypted in Postgres; GMAIL_TOKEN_FILE only supports legacy local data.
mkdir -p /app/data/chromadb /app/data/gmail
alembic upgrade head

shutdown() {
  trap - INT TERM EXIT
  [ -n "${api_pid:-}" ] && kill "$api_pid" 2>/dev/null || true
  [ -n "${worker_supervisor_pid:-}" ] && kill "$worker_supervisor_pid" 2>/dev/null || true
  wait 2>/dev/null || true
}

# A background worker must not silently disappear while the HTTP process is
# healthy. Restart it with a small backoff, while allowing Render to terminate
# both processes cleanly during a deploy.
run_worker() {
  while true; do
    celery -A app.workers.celery_app:celery_app worker --loglevel="${LOG_LEVEL:-info}" --concurrency="${CELERY_CONCURRENCY:-2}"
    worker_exit=$?
    echo "Celery worker exited with status ${worker_exit}; restarting in 5 seconds." >&2
    sleep 5
  done
}

trap 'shutdown; exit 0' INT TERM
run_worker &
worker_supervisor_pid=$!

uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" &
api_pid=$!
wait "$api_pid"
api_exit=$?
shutdown
exit "$api_exit"
