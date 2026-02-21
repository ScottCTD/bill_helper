#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"

mkdir -p "$LOG_DIR"

BACKEND_LOG="$LOG_DIR/backend-$TIMESTAMP.log"
FRONTEND_LOG="$LOG_DIR/frontend-$TIMESTAMP.log"

BACKEND_PID=""
FRONTEND_PID=""
SHUTTING_DOWN=0

cleanup() {
  if [[ "$SHUTTING_DOWN" -eq 1 ]]; then
    return
  fi
  SHUTTING_DOWN=1

  echo
  echo "Stopping backend/frontend..."

  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait "$BACKEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true
}

on_interrupt() {
  cleanup
  exit 130
}

trap on_interrupt INT TERM

cd "$ROOT_DIR"

echo "Checking migration metadata..."
if uv run python -c "from backend.database import SessionLocal; from backend.services.bootstrap import should_stamp_existing_schema; db = SessionLocal(); should_stamp = should_stamp_existing_schema(db); db.close(); raise SystemExit(0 if should_stamp else 1)"; then
  echo "Detected existing schema without Alembic revision metadata. Stamping head..."
  uv run alembic stamp head
fi

echo "Applying database migrations..."
uv run alembic upgrade head

echo "Checking whether demo seed is needed..."
if uv run python -c "from backend.database import SessionLocal; from backend.services.bootstrap import should_seed_demo_data; db = SessionLocal(); should_seed = should_seed_demo_data(db); db.close(); raise SystemExit(0 if should_seed else 1)"; then
  echo "No accounts found. Seeding demo data..."
  uv run python scripts/seed_demo.py
else
  echo "Existing accounts found. Skipping demo seed."
fi

echo "Syncing frontend dependencies..."
(
  cd "$ROOT_DIR/frontend"
  npm install
)

echo "Starting backend (log: $BACKEND_LOG)"
uv run bill-helper-api > >(tee "$BACKEND_LOG") 2>&1 &
BACKEND_PID=$!

echo "Starting frontend (log: $FRONTEND_LOG)"
(
  cd "$ROOT_DIR/frontend"
  npm run dev
) > >(tee "$FRONTEND_LOG") 2>&1 &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Frontend URL: http://localhost:5173"
echo "Backend API:  http://localhost:8000/api/v1"
echo "Backend Docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop both services."

set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
EXIT_STATUS=$?
set -e

if [[ "$SHUTTING_DOWN" -eq 0 ]]; then
  echo
  echo "A service exited unexpectedly. Shutting down both services..."
fi

cleanup

exit "$EXIT_STATUS"
