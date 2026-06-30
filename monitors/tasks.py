import time

import requests
from celery import shared_task
from django.utils import timezone

from .models import CheckLog, Monitor


@shared_task
def check_monitor(monitor_id):
    try:
        monitor = Monitor.objects.get(pk=monitor_id)
    except Monitor.DoesNotExist:
        return

    status_code = None
    response_time_ms = None
    success = False
    error_message = ""

    try:
        start = time.monotonic()
        response = requests.get(
            monitor.url,
            timeout=10,
            allow_redirects=True,
            headers={"User-Agent": "UptimeMonitor/1.0"},
        )
        elapsed = time.monotonic() - start
        response_time_ms = int(elapsed * 1000)
        status_code = response.status_code
        success = response.status_code < 400
    except requests.Timeout:
        error_message = "Request timed out"
    except requests.ConnectionError:
        error_message = "Connection error"
    except requests.TooManyRedirects:
        error_message = "Too many redirects"
    except requests.RequestException as exc:
        error_message = str(exc)[:255]

    CheckLog.objects.create(
        monitor=monitor,
        status_code=status_code,
        response_time_ms=response_time_ms,
        success=success,
        error_message=error_message,
    )

    new_status = Monitor.Status.UP if success else Monitor.Status.DOWN
    Monitor.objects.filter(pk=monitor_id).update(
        current_status=new_status,
        last_checked_at=timezone.now(),
    )


@shared_task
def check_all_monitors():
    monitor_ids = Monitor.objects.values_list("id", flat=True)
    for monitor_id in monitor_ids:
        check_monitor.delay(monitor_id)
