import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send(channel, subject, body):
    """Send via a self-hosted Push Relay (Web Push) service.

    The subscriber label is per-channel; the service URL + bearer key are app-level settings.
    """
    if not channel.push_relay_label:
        return

    base_url = getattr(settings, "PUSH_RELAY_URL", "")
    send_key = getattr(settings, "PUSH_RELAY_SEND_KEY", "")
    if not base_url or not send_key:
        logger.warning("Push Relay not configured (PUSH_RELAY_URL / PUSH_RELAY_SEND_KEY)")
        return

    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/send",
        json={
            "label": channel.push_relay_label,
            "notification": {"title": subject, "body": body},
        },
        headers={
            "Authorization": f"Bearer {send_key}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    response.raise_for_status()
