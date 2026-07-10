import logging

from .models import NotificationChannel, NotificationPreference

logger = logging.getLogger(__name__)

# Backend registry: ChannelType value → callable(channel, subject, body)
BACKENDS = {}


def _register_backends():
    """Lazily import and register all backends."""
    if BACKENDS:
        return
    from .backends import push_relay_backend, slack_backend, sms_backend, webhook_backend

    BACKENDS[NotificationChannel.ChannelType.WEBHOOK] = webhook_backend.send
    BACKENDS[NotificationChannel.ChannelType.SLACK] = slack_backend.send
    BACKENDS[NotificationChannel.ChannelType.SMS] = sms_backend.send
    BACKENDS[NotificationChannel.ChannelType.PUSH_RELAY] = push_relay_backend.send


def send_notification(user, subject, body, category=None, category_label=None):
    # 1. Check category preference
    if category:
        pref, _ = NotificationPreference.objects.get_or_create(
            user=user,
            category=category,
            defaults={"label": category_label or category, "enabled": True},
        )
        if not pref.enabled:
            return

    # 2. Always send email
    from .email import send_email_backend

    send_email_backend(user, subject, body)

    # 3. Send to each enabled channel
    _register_backends()
    channels = NotificationChannel.objects.filter(user=user, enabled=True)
    for channel in channels:
        backend = BACKENDS.get(channel.channel_type)
        if not backend:
            logger.warning("No backend for channel type %s", channel.channel_type)
            continue
        try:
            backend(channel, subject, body)
        except Exception:
            logger.exception(
                "Failed to send via %s channel %s", channel.channel_type, channel.pk
            )
