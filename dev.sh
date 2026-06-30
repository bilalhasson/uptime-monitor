#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/venv"

if [ ! -d "$VENV" ]; then
  echo "Error: venv not found at $VENV"
  echo "Run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
  exit 1
fi

cd "$DIR"
PYTHON="$VENV/bin/python"
CELERY="$VENV/bin/celery"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $PID_SERVER $PID_WORKER $PID_BEAT 2>/dev/null
  docker compose -f "$DIR/docker-compose.yml" down
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT

echo "Starting Redis..."
docker compose -f "$DIR/docker-compose.yml" up -d

echo "Applying migrations..."
"$PYTHON" manage.py migrate --run-syncdb

echo "Starting Django dev server..."
"$PYTHON" manage.py runserver &
PID_SERVER=$!

echo "Starting Celery worker..."
"$CELERY" -A uptime_monitor worker --loglevel=info &
PID_WORKER=$!

echo "Starting Celery beat..."
"$CELERY" -A uptime_monitor beat --loglevel=info &
PID_BEAT=$!

echo ""
echo "All services running. Press Ctrl+C to stop."
wait
