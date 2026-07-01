import logging

import requests

logger = logging.getLogger(__name__)


def send(channel, subject, body):
    if not channel.slack_access_token or not channel.slack_channel_id:
        return

    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {channel.slack_access_token}",
            "Content-Type": "application/json",
        },
        json={
            "channel": channel.slack_channel_id,
            "text": f"*{subject}*\n{body}",
        },
        timeout=10,
    )
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
