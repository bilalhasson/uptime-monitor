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
