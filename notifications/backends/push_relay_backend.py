import logging

from django.conf import settings
from push_relay import PushRelay

logger = logging.getLogger(__name__)


def send(channel, subject, body, url=None):
    """Send via a self-hosted Push Relay (Web Push) service, through the ``push-relay`` SDK.

    The subscriber label is per-channel; the service URL + bearer key are app-level settings.
    ``url`` (if given) becomes the notification's click-to-open target. Transport is the SDK's job
    (retries, typed errors); dispatch logs any raised error per channel.
    """
    if not channel.push_relay_label:
        return

    base_url = getattr(settings, "PUSH_RELAY_URL", "")
    send_key = getattr(settings, "PUSH_RELAY_SEND_KEY", "")
    if not base_url or not send_key:
        logger.warning("Push Relay not configured (PUSH_RELAY_URL / PUSH_RELAY_SEND_KEY)")
        return

    PushRelay(base_url, send_key).send(
        channel.push_relay_label, title=subject, body=body, url=url
    )
