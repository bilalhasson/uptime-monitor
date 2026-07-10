import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send(channel, subject, body, url=None):
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "")

    if not account_sid or not channel.sms_phone_number:
        return

    from twilio.rest import Client

    text = f"{subject}\n{body}"
    if len(text) > 1600:
        text = text[:1597] + "..."

    client = Client(account_sid, auth_token)
    client.messages.create(
        to=channel.sms_phone_number,
        from_=from_number,
        body=text,
    )
