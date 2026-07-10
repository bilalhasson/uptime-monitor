import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send(channel, subject, body, url=None):
    """Send via a self-hosted Push Relay (Web Push) service.

    The subscriber label is per-channel; the service URL + bearer key are app-level settings.
    ``url`` (if given) becomes the notification's click-to-open target.
    """
    if not channel.push_relay_label:
        return

    base_url = getattr(settings, "PUSH_RELAY_URL", "")
    send_key = getattr(settings, "PUSH_RELAY_SEND_KEY", "")
    if not base_url or not send_key:
        logger.warning("Push Relay not configured (PUSH_RELAY_URL / PUSH_RELAY_SEND_KEY)")
        return

    notification = {"title": subject, "body": body}
    if url:
        notification["url"] = url

    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/send",
        json={"label": channel.push_relay_label, "notification": notification},
        headers={
            "Authorization": f"Bearer {send_key}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    response.raise_for_status()
