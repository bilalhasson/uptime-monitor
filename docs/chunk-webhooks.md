# Chunk 13 — Webhook Notifications & Dispatch Foundation

## Context

The app sends all notifications via email only (Resend API). This chunk adds
generic webhook notifications and builds the multi-channel dispatch foundation
that Slack and SMS chunks will build on. Users configure a webhook URL in
settings; the app POSTs JSON to it for every notification event.

## Architecture

Current flow:
```
Celery task → monitors/notifications.py → notifications/email.py send_email() → Resend API
```

New flow:
```
Celery task → monitors/notifications.py → notifications/dispatch.py send_notification()
                                               ├─ email backend (Resend, always)
                                               └─ webhook backend (POST JSON)
```

Category preferences (`NotificationPreference`) remain global gatekeepers.
Email is the implicit default channel (no record needed). Additional channels
are stored in a new `NotificationChannel` model.

## Model: `NotificationChannel` (`notifications/models.py`)

Single-table design — all channel types share one model. This chunk only uses
webhook fields; Slack and SMS fields are included now to avoid future migrations.

```python
class NotificationChannel(models.Model):
    class ChannelType(models.TextChoices):
        SLACK = "slack", "Slack"
        WEBHOOK = "webhook", "Webhook"
        SMS = "sms", "SMS"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notification_channels")
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    label = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)

    # Slack (used in chunk-slack)
    slack_access_token = models.CharField(max_length=512, blank=True, default="")
    slack_channel_id = models.CharField(max_length=100, blank=True, default="")
    slack_channel_name = models.CharField(max_length=200, blank=True, default="")
    slack_team_name = models.CharField(max_length=200, blank=True, default="")

    # Webhook
    webhook_url = models.URLField(max_length=2048, blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")

    # SMS (used in chunk-sms)
    sms_phone_number = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.get_channel_type_display()}: {self.label}"
```

## Dispatch (`notifications/dispatch.py` — new file)

```python
def send_notification(user, subject, body, category=None, category_label=None):
    # 1. Check category preference (same get_or_create logic as old send_email)
    #    Return early if category disabled
    # 2. Always call email backend (send_email_backend)
    # 3. For each enabled NotificationChannel for this user:
    #      call the matching backend in try/except, log errors, continue
```

Backend registry dict maps `ChannelType` → backend `send()` function. This chunk
registers only the webhook backend; Slack and SMS chunks add theirs.

## Refactor `notifications/email.py`

- Extract delivery logic into `send_email_backend(user, subject, body)` — no
  preference checking, just Resend API call
- Keep `send_email()` as backward-compatible wrapper that calls `send_notification()`
  (avoids breaking any direct callers)

## Webhook backend (`notifications/backends/webhook_backend.py`)

```python
def send(channel, subject, body):
    # POST JSON {"subject": ..., "body": ...} to channel.webhook_url
    # Include X-Webhook-Secret header if channel.webhook_secret is set
    # timeout=10, raise_for_status()
    # Skip if webhook_url is empty
```

Also create `notifications/backends/__init__.py` (empty).

## Update `monitors/notifications.py`

Change import from `send_email` to `send_notification` from `notifications.dispatch`.
Same 4 wrapper functions, same signatures — just call `send_notification()` instead.
`monitors/tasks.py` requires zero changes.

## Settings UI

**Expand `/settings/emails/` → `/settings/notifications/`** (old URL redirects).

One page with two sections:
1. **Notification Categories** — same checkboxes as before
2. **Notification Channels** — list configured channels with toggle/delete,
   plus "Add Webhook" button (Slack and SMS buttons added in later chunks)

**New views in `notifications/views.py`**:
- `notification_settings_view` — main page (GET shows form + channels, POST saves prefs)
- `add_webhook_channel_view` — form with label, URL, optional secret
- `toggle_channel_view(request, channel_id)` — POST to toggle enabled
- `delete_channel_view(request, channel_id)` — POST to delete
- `email_preferences_redirect` — redirect old URL to new one

**New file: `notifications/forms.py`**:
- `WebhookChannelForm(ModelForm)` — fields: label, webhook_url, webhook_secret

## URL routes (`notifications/urls.py`)

```python
path("settings/notifications/", views.notification_settings_view, name="notification-settings"),
path("settings/emails/", views.email_preferences_redirect, name="email-preferences"),
path("settings/notifications/add-webhook/", views.add_webhook_channel_view, name="add-webhook-channel"),
path("settings/notifications/channels/<int:channel_id>/toggle/", views.toggle_channel_view, name="toggle-channel"),
path("settings/notifications/channels/<int:channel_id>/delete/", views.delete_channel_view, name="delete-channel"),
```

## Other file changes

- `monitors/templates/base.html:48` — change `{% url 'email-preferences' %}` to `{% url 'notification-settings' %}`
- `notifications/admin.py` — register `NotificationChannel`

## Templates

- `notifications/templates/notifications/notification_settings.html` — main settings page
- `notifications/templates/notifications/add_webhook.html` — webhook form

## Files inventory

| Action | File |
|--------|------|
| Modify | `notifications/models.py` — add `NotificationChannel` |
| Modify | `notifications/email.py` — extract `send_email_backend`, wrapper |
| Create | `notifications/dispatch.py` — `send_notification()` dispatcher |
| Create | `notifications/backends/__init__.py` |
| Create | `notifications/backends/webhook_backend.py` |
| Create | `notifications/forms.py` — `WebhookChannelForm` |
| Modify | `notifications/views.py` — settings view, channel CRUD, redirect |
| Modify | `notifications/urls.py` — new routes |
| Modify | `notifications/admin.py` — register `NotificationChannel` |
| Create | `notifications/templates/notifications/notification_settings.html` |
| Create | `notifications/templates/notifications/add_webhook.html` |
| Modify | `monitors/notifications.py` — use `send_notification` |
| Modify | `monitors/templates/base.html` — update nav link |
| Modify | `notifications/tests.py` — add tests |
| Auto   | `notifications/migrations/0002_notificationchannel.py` |

**Unchanged**: `monitors/tasks.py`, `monitors/models.py`, `monitors/views.py`,
`uptime_monitor/settings.py` (no new env vars needed for webhooks)

## Tests (~25)

**Model** (~5): create webhook channel, str repr, default enabled, cascade delete, channel types

**Dispatch** (~6): email-only when no channels, sends to all enabled, skips disabled,
category disabled skips everything, backend failure doesn't block others, no-category
sends to all

**Webhook backend** (~4): correct payload, secret header included when set, no header
when blank, raises on HTTP error

**Views** (~10): notification_settings login/get/post, add_webhook form valid/invalid,
toggle channel, delete channel, other-user 404s, old URL redirect

## Verification

```bash
python3 manage.py makemigrations notifications
python3 manage.py migrate
python3 manage.py test
python3 manage.py test notifications
python3 manage.py test monitors
```
