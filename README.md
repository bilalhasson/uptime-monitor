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
4. **Pause/resume** — toggle monitoring on or off without deleting the monitor.
5. **Monitor detail** — click a monitor to see check history, uptime percentage, and average response time.
6. **Edit/delete** — update a monitor's settings or remove it entirely (all check history is deleted with it).
7. **Email preferences** — visit `/settings/emails/` to control which notification types you receive.

## Email notifications

Email alerts are sent via [Resend](https://resend.com) when a monitor transitions
between **up** and **down** states. The first check (pending to up/down) is silent.
A confirmation email is also sent when a new monitor is added.

Set these environment variables to enable notifications:

```
RESEND_API_KEY     = <your Resend API key>
DEFAULT_FROM_EMAIL = "UptimeMonitor <noreply@yourdomain.com>"
```

When `RESEND_API_KEY` is empty (the default), notifications are skipped and a
warning is logged. Monitor owners must have an email address on their user
account to receive alerts.

### Per-user preferences

Users can opt out of individual notification categories at `/settings/emails/`.
Three categories are available:

- **Monitor added** — confirmation when a new monitor is created
- **Monitor goes down** — alert when a monitored URL starts failing
- **Monitor recovers** — alert when a monitored URL comes back up

Preferences are created automatically on first use. The `notifications` app is
fully decoupled from `monitors` — it provides generic category-based email
delivery, while monitor-specific content is composed in `monitors/notifications.py`.

## Error tracking (Sentry)

Errors and performance data are reported to [Sentry](https://sentry.io) via the
`sentry-sdk[django,celery]` package. Sentry is enabled only when a DSN is set;
if `SENTRY_DSN` is empty (the default), the SDK is never initialised and the app
runs without any reporting.

Set these environment variables to enable it:

```
SENTRY_DSN     = <your Sentry project DSN>
SENTRY_RELEASE = <release identifier>   # optional; set automatically in CI
```

Configuration (see `uptime_monitor/settings.py`):

- **Django & Celery integrations** — requests, background tasks, and unhandled
  exceptions are captured automatically.
- **Logging integration** — log records at `ERROR` level and above are sent as
  Sentry events. Note this means handled errors that are logged via
  `logger.exception(...)` (e.g. a single failing notification channel in
  `notifications/dispatch.py`) still surface as Sentry issues.
- **`traces_sample_rate=0.1`** — 10% of transactions are sampled for performance
  monitoring.
- **`send_default_pii=False`** — user PII is not attached to events.
- **`environment`** — `production` when `DEBUG` is off, otherwise `development`.

### Releases

The CI workflow (`.github/workflows/ci.yml`) creates a Sentry release on every
push to `main` after tests pass. It uses the Sentry CLI to register the release,
associate commits (`set-commits --auto`), and finalize it, which links errors to
the commit that introduced them. This requires a `SENTRY_AUTH_TOKEN` secret in
the GitHub repo; the org (`bilal-hasson`) and project (`python-django`) are set
in the workflow.

## Deployment

Deployed on Railway. See [DEPLOY.md](DEPLOY.md) for setup instructions.

## Credentials

Production secrets (e.g. `SECRET_KEY`) are stored in **Bitwarden** under the
`deploy/uptime-monitor` item — that vault is the source of truth for recovery
and rotation. Live values are set as environment variables on Railway and are
never committed to this repo. `DATABASE_URL` and `REDIS_URL` are provided by
Railway's Postgres/Redis plugins, not stored in the vault.
