# Uptime Monitor

A Django application that monitors website uptime by periodically checking URLs and recording results. Sends email notifications via [Resend](https://resend.com) when a monitor goes down or recovers.

**Live at [uptime.bilalhasson.com](https://uptime.bilalhasson.com)**

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

## Usage

1. **Sign up** at `/signup/` (or log in at `/login/`).
2. **Add a monitor** — paste a URL into the input on the dashboard and click "Add".
3. **View status** — monitors show a colored dot: green (up), red (down), or grey (pending). Status updates automatically as the background checker runs.
4. **Delete a monitor** — click "Delete" next to any monitor, then confirm on the next page. All check history for that monitor is removed.

## Email notifications

Email alerts are sent via [Resend](https://resend.com) when a monitor transitions
between **up** and **down** states. The first check (pending to up/down) is silent.

Set these environment variables to enable notifications:

```
RESEND_API_KEY     = <your Resend API key>
DEFAULT_FROM_EMAIL = "UptimeMonitor <noreply@yourdomain.com>"
```

When `RESEND_API_KEY` is empty (the default), notifications are skipped and a
warning is logged. Monitor owners must have an email address on their user
account to receive alerts.

## Deployment

Deployed on Railway. See [DEPLOY.md](DEPLOY.md) for setup instructions.

## Credentials

Production secrets (e.g. `SECRET_KEY`) are stored in **Bitwarden** under the
`deploy/uptime-monitor` item — that vault is the source of truth for recovery
and rotation. Live values are set as environment variables on Railway and are
never committed to this repo. `DATABASE_URL` and `REDIS_URL` are provided by
Railway's Postgres/Redis plugins, not stored in the vault.
