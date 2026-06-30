import logging

import resend
from django.conf import settings

logger = logging.getLogger(__name__)


def send_monitor_down_email(monitor):
    subject = f"ALERT: {monitor.url} is DOWN"
    body = (
        f"Your monitor for {monitor.url} is now DOWN.\n\n"
        f"Last checked at: {monitor.last_checked_at}\n\n"
        "We'll notify you when it recovers."
    )
    _send_status_email(monitor, subject, body)


def send_monitor_recovery_email(monitor):
    subject = f"RECOVERED: {monitor.url} is back UP"
    body = (
        f"Your monitor for {monitor.url} has RECOVERED and is back UP.\n\n"
        f"Last checked at: {monitor.last_checked_at}"
    )
    _send_status_email(monitor, subject, body)


def _send_status_email(monitor, subject, body):
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email notification")
        return

    recipient = monitor.owner.email
    if not recipient:
        logger.info("Monitor %s owner has no email — skipping notification", monitor.id)
        return

    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [recipient],
                "subject": subject,
                "text": body,
            }
        )
        logger.info("Sent notification email to %s for monitor %s", recipient, monitor.id)
    except Exception:
        logger.exception("Failed to send notification email for monitor %s", monitor.id)
