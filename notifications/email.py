import logging

import resend
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email_backend(user, subject, body):
    """Deliver an email via Resend. No preference checking."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email")
        return

    recipient = user.email
    if not recipient:
        logger.info("User %s has no email — skipping", user.pk)
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
        logger.info("Sent email to %s", recipient)
    except Exception:
        logger.exception("Failed to send email to %s", recipient)


def send_email(user, subject, body, category=None, category_label=None):
    """Backward-compatible wrapper — delegates to dispatch."""
    from .dispatch import send_notification

    send_notification(
        user=user,
        subject=subject,
        body=body,
        category=category,
        category_label=category_label,
    )
