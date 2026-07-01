import ssl
import socket
import time
import datetime as dt
from urllib.parse import urlparse

import certifi
import requests
from celery import shared_task
from django.utils import timezone

from .models import CheckLog, Monitor
from .notifications import (
    send_monitor_down_email,
    send_monitor_recovery_email,
    send_ssl_expiring_email,
)


@shared_task
def check_monitor(monitor_id):
    try:
        monitor = Monitor.objects.select_related("owner").get(pk=monitor_id)
    except Monitor.DoesNotExist:
        return

    if monitor.is_paused:
        return

    previous_status = monitor.current_status

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
    now = timezone.now()
    Monitor.objects.filter(pk=monitor_id).update(
        current_status=new_status,
        last_checked_at=now,
    )

    # Update in-memory instance so notification functions see current values
    monitor.current_status = new_status
    monitor.last_checked_at = now

    # Notify on real transitions only (skip initial pending → up/down)
    if previous_status != new_status and previous_status != Monitor.Status.PENDING:
        if new_status == Monitor.Status.DOWN:
            send_monitor_down_email(monitor)
        elif new_status == Monitor.Status.UP:
            send_monitor_recovery_email(monitor)


@shared_task
def check_all_monitors():
    monitor_ids = Monitor.objects.filter(is_paused=False).values_list("id", flat=True)
    for monitor_id in monitor_ids:
        check_monitor.delay(monitor_id)


@shared_task
def check_ssl_certificate(monitor_id):
    try:
        monitor = Monitor.objects.select_related("owner").get(pk=monitor_id)
    except Monitor.DoesNotExist:
        return

    if monitor.is_paused:
        return

    if not monitor.url.lower().startswith("https://"):
        return

    parsed = urlparse(monitor.url)
    hostname = parsed.hostname
    port = parsed.port or 443

    now = timezone.now()
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        expiry_str = cert["notAfter"]
        expiry_date = timezone.make_aware(
            dt.datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z"),
            timezone=dt.timezone.utc,
        )

        issuer_parts = dict(x[0] for x in cert.get("issuer", ()))
        issuer = issuer_parts.get("organizationName", "")

        old_expiry = monitor.ssl_expiry_date

        monitor.ssl_expiry_date = expiry_date
        monitor.ssl_issuer = issuer
        monitor.ssl_last_checked_at = now
        monitor.ssl_error = ""

        # Reset notification flag if cert was renewed (expiry date changed)
        if old_expiry and old_expiry != expiry_date:
            monitor.ssl_expiry_notified = False

        # Notify if expiring within 14 days and not yet notified
        days_remaining = (expiry_date - now).days
        if days_remaining < 14 and not monitor.ssl_expiry_notified:
            send_ssl_expiring_email(monitor, days_remaining)
            monitor.ssl_expiry_notified = True

        monitor.save(update_fields=[
            "ssl_expiry_date",
            "ssl_issuer",
            "ssl_last_checked_at",
            "ssl_error",
            "ssl_expiry_notified",
        ])

    except (socket.error, ssl.SSLError, OSError) as exc:
        monitor.ssl_error = str(exc)[:255]
        monitor.ssl_expiry_date = None
        monitor.ssl_last_checked_at = now
        monitor.save(update_fields=[
            "ssl_error",
            "ssl_expiry_date",
            "ssl_last_checked_at",
        ])


@shared_task
def check_all_ssl_certificates():
    monitor_ids = (
        Monitor.objects.filter(is_paused=False, url__istartswith="https://")
        .values_list("id", flat=True)
    )
    for monitor_id in monitor_ids:
        check_ssl_certificate.delay(monitor_id)
