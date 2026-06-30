# Process types for production deployment (Heroku, Railway, etc.)
web: python manage.py migrate --noinput && gunicorn uptime_monitor.wsgi --bind 0.0.0.0:$PORT
worker: celery -A uptime_monitor worker --loglevel=info
beat: celery -A uptime_monitor beat --loglevel=info
