import os
import warnings

from celery import Celery
from celery.exceptions import SecurityWarning

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uptime_monitor.settings")

# Celery emits this warning unconditionally when the worker runs as root, which
# it always does inside Railway's isolated containers. C_FORCE_ROOT does NOT
# suppress it (that flag only bypasses the pickle-specific ROOT_DISALLOWED
# error, and we use JSON), so filter the warning here instead.
warnings.filterwarnings(
    "ignore",
    category=SecurityWarning,
    message="You're running the worker with superuser privileges",
)

app = Celery("uptime_monitor")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
