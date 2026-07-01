# Deploying to Railway

This project deploys as **5 components** from this single GitHub repo:

| Component | Type | Start command |
|-----------|------|---------------|
| **web** | service (gunicorn) | Procfile default: `migrate && gunicorn --bind 0.0.0.0:$PORT` |
| **worker** | service (Celery) | `celery -A uptime_monitor worker --loglevel=info` |
| **beat** | service (Celery) | `celery -A uptime_monitor beat --loglevel=info` |
| **PostgreSQL** | Railway database | provides `DATABASE_URL` |
| **Redis** | Railway database | provides `REDIS_URL` |

## Setup checklist

1. **Add databases** — in the project canvas: **+ New → Database → PostgreSQL**, then **→ Redis**.
2. **web service variables** (Variables tab):
   ```
   SECRET_KEY       = <unique per project — see Credentials>
   DEBUG            = False
   DATABASE_URL     = ${{Postgres.DATABASE_URL}}
   REDIS_URL        = ${{Redis.REDIS_URL}}
   RESEND_API_KEY   = <Resend API key — see Credentials>
   DEFAULT_FROM_EMAIL = "UptimeMonitor <noreply@yourdomain.com>"
   ```
   `RAILWAY_PUBLIC_DOMAIN` is injected automatically — `ALLOWED_HOSTS` and
   `CSRF_TRUSTED_ORIGINS` pick it up in `settings.py`.
3. **worker service** — **+ New → GitHub Repo** (same repo), then:
   - Settings → Deploy → Custom Start Command: `celery -A uptime_monitor worker --loglevel=info`
   - Variables: `DATABASE_URL`, `REDIS_URL`, `RESEND_API_KEY`
4. **beat service** — same again:
   - Custom Start Command: `celery -A uptime_monitor beat --loglevel=info`
   - Variables: `DATABASE_URL`, `REDIS_URL`
5. **Create a superuser** (optional) — monitors are managed through the UI by
   any logged-in user. A superuser is only needed for Django admin access:
   ```
   python manage.py createsuperuser
   ```

Tip: use Railway **project-level shared variables** for values common to all
three services so you set them once instead of per service.

## Running Celery as root

Celery emits a `SecurityWarning` ("running the worker with superuser
privileges") whenever it runs as root, which it always does inside Railway's
isolated containers. This is safe here — the container is a throwaway sandbox.

Note: `C_FORCE_ROOT` does **not** silence this warning (it only bypasses a
separate pickle-specific error that doesn't apply when using JSON
serialization). The warning is filtered directly in `uptime_monitor/celery.py`
via `warnings.filterwarnings(...)`, so no env var is needed. A non-root `--uid`
would be the textbook fix but isn't practical under Nixpacks.

## Credentials

Production secrets are stored in **Bitwarden** under a `deploy/<project>` item
— that vault is the source of truth for recovery and rotation. Conventions:

- **`RESEND_API_KEY`** — obtain from the [Resend dashboard](https://resend.com).
  Required on the **web** and **worker** services for email notifications.
  Without it notifications are silently skipped.
- **Unique `SECRET_KEY` per project** — never reuse across apps. Generate with:
  ```
  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- Real values live only as Railway env vars — never commit them.
- `DATABASE_URL` / `REDIS_URL` are managed by Railway's plugins via `${{...}}`
  references; don't copy them into the vault (they rotate on Railway's side).
- Local dev uses a gitignored `.env` with throwaway values.
