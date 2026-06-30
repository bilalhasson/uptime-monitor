# Process types for production deployment (Heroku, Railway, etc.)
web: gunicorn uptime_monitor.wsgi
worker: celery -A uptime_monitor worker --loglevel=info
beat: celery -A uptime_monitor beat --loglevel=info
