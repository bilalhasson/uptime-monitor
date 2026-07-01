# Chunk 15 — SMS Notifications (Twilio)

## Context

Builds on Chunk 13 (webhook foundation). Adds SMS as a notification channel via
Twilio. Users add a phone number in notification settings; the app sends SMS for
every notification event. See `docs/twilio-sms.md` for Twilio account setup,
test credentials, magic numbers, and UK Sender ID registration.

**Prerequisite**: Chunk 13 must be implemented first (provides `NotificationChannel`
model, dispatch system, settings UI, backends package).

## SMS backend (`notifications/backends/sms_backend.py` — new file)

```python
from twilio.rest import Client

def send(channel, subject, body):
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_FROM_NUMBER

    # Skip if not configured
    if not account_sid or not channel.sms_phone_number:
        return

    # SMS is length-constrained; truncate
    text = f"{subject}\n{body}"
    if len(text) > 1600:
        text = text[:1597] + "..."

    client = Client(account_sid, auth_token)
    client.messages.create(
        to=channel.sms_phone_number,
        from_=from_number,
        body=text,
    )
```

Register in `notifications/dispatch.py` BACKENDS dict.

## Add SMS form

**Add to `notifications/forms.py`**:
```python
class SMSChannelForm(ModelForm):
    class Meta:
        model = NotificationChannel
        fields = ("label", "sms_phone_number")
```

**New view in `notifications/views.py`**:
- `add_sms_channel_view` — form with label and phone number (E.164 format)

**New template**: `notifications/templates/notifications/add_sms.html`

## URL routes

Add to `notifications/urls.py`:
```python
path("settings/notifications/add-sms/", views.add_sms_channel_view, name="add-sms-channel"),
```

## Settings changes (`uptime_monitor/settings.py`)

```python
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
```

## Dependencies

Add to `requirements.txt`:
```
twilio
```

## Template changes

Update `notification_settings.html` to add an "Add SMS" button that links to
`{% url 'add-sms-channel' %}`.

## Files inventory

| Action | File |
|--------|------|
| Create | `notifications/backends/sms_backend.py` |
| Create | `notifications/templates/notifications/add_sms.html` |
| Modify | `notifications/dispatch.py` — register SMS backend |
| Modify | `notifications/forms.py` — add `SMSChannelForm` |
| Modify | `notifications/views.py` — add `add_sms_channel_view` |
| Modify | `notifications/urls.py` — add SMS route |
| Modify | `notifications/templates/notifications/notification_settings.html` — add SMS button |
| Modify | `uptime_monitor/settings.py` — add Twilio settings |
| Modify | `requirements.txt` — add `twilio` |
| Modify | `notifications/tests.py` — add SMS tests |

## Tests (~7)

**SMS backend** (~4): correct Twilio client call, skips when no account SID,
skips when no phone number, truncates long messages

**SMS view** (~3): login required, valid post creates channel, renders form on GET

## Verification

```bash
pip install twilio
python3 manage.py test notifications
python3 manage.py test monitors
```

Manual: set Twilio test credentials (see `docs/twilio-sms.md` Step 1),
add an SMS channel with magic number `+15005550006`, trigger a notification,
verify Twilio API is called without error.
