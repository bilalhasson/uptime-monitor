# Uptime Monitor

A Django application that monitors website uptime by periodically checking URLs and recording results.

## Prerequisites

- Python 3.12+
- Docker (for Redis)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

## Running locally

The quickest way to start everything (Redis, Django, Celery worker, Celery beat):

```bash
./dev.sh
```

Press Ctrl+C to stop all services.

### Manual startup

If you prefer running each process separately:

```bash
# Start Redis
docker compose up -d

# In separate terminals (with venv activated):
python manage.py runserver
celery -A uptime_monitor worker --loglevel=info
celery -A uptime_monitor beat --loglevel=info

# To stop Redis
docker compose down
```

## Credentials

Production secrets (e.g. `SECRET_KEY`) are stored in **Bitwarden** under the
`deploy/uptime-monitor` item — that vault is the source of truth for recovery
and rotation. Live values are set as environment variables on Railway and are
never committed to this repo. `DATABASE_URL` and `REDIS_URL` are provided by
Railway's Postgres/Redis plugins, not stored in the vault.
