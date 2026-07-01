import logging

import requests

logger = logging.getLogger(__name__)


def send(channel, subject, body):
    if not channel.webhook_url:
        return

    headers = {"Content-Type": "application/json"}
    if channel.webhook_secret:
        headers["X-Webhook-Secret"] = channel.webhook_secret

    response = requests.post(
        channel.webhook_url,
        json={"subject": subject, "body": body},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
