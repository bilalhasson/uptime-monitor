import logging

import resend
from django.conf import settings

from .models import NotificationPreference

logger = logging.getLogger(__name__)


def send_email(user, subject, body, category=None, category_label=None):
    if category:
        pref, _ = NotificationPreference.objects.get_or_create(
            user=user,
            category=category,
            defaults={"label": category_label or category, "enabled": True},
        )
        if not pref.enabled:
            return

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
        logger.info("Sent '%s' email to %s", category or "uncategorized", recipient)
    except Exception:
        logger.exception("Failed to send email to %s", recipient)
