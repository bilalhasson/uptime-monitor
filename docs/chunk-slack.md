# Chunk 14 — Slack Notifications (OAuth App)

## Context

Builds on Chunk 13 (webhook foundation). Adds Slack as a notification channel
via a full OAuth app integration. Users click "Connect Slack" in notification
settings, authorize via Slack's OAuth flow, and select a channel. Notifications
are posted to that channel via `chat.postMessage`.

**Prerequisite**: Chunk 13 must be implemented first (provides `NotificationChannel`
model, dispatch system, settings UI, backends package).

## Slack OAuth flow

1. User clicks "Connect Slack" on `/settings/notifications/`
2. App redirects to `https://slack.com/oauth/v2/authorize` with `client_id`,
   `scope=chat:write,incoming_webhook`, `redirect_uri`, `state`
3. User authorizes and selects a channel in Slack's UI
4. Slack redirects back to callback URL with `code` and `state`
5. App exchanges `code` for `access_token` via `POST /api/oauth.v2.access`
6. App creates `NotificationChannel(channel_type="slack")` with token and channel info
7. User redirected to settings page with success message

## Slack backend (`notifications/backends/slack_backend.py` — new file)

```python
def send(channel, subject, body):
    # POST to https://slack.com/api/chat.postMessage
    # Auth: Bearer {channel.slack_access_token}
    # Body: {"channel": channel.slack_channel_id, "text": "*{subject}*\n{body}"}
    # Check response.json()["ok"], raise on error
    # Skip if no token or channel_id
```

Register in `notifications/dispatch.py` BACKENDS dict.

## OAuth views (`notifications/views_slack.py` — new file)

**`slack_oauth_initiate(request)`**:
- Generate random state via `secrets.token_urlsafe(32)`, store in session
- Build Slack authorize URL with `client_id`, `scope`, `redirect_uri`, `state`
- Return redirect

**`slack_oauth_callback(request)`**:
- Check for `error` query param (user denied)
- Verify `state` matches session value
- Exchange `code` for token: `POST https://slack.com/api/oauth.v2.access`
  with `client_id`, `client_secret`, `code`, `redirect_uri`
- Extract from response: `access_token`, `team.name`,
  `incoming_webhook.channel_id`, `incoming_webhook.channel`
- Create `NotificationChannel` record
- Redirect to `notification-settings` with success message

## URL routes

Add to `notifications/urls.py`:

```python
path("settings/notifications/slack/connect/", views_slack.slack_oauth_initiate, name="slack-oauth-initiate"),
path("settings/notifications/slack/callback/", views_slack.slack_oauth_callback, name="slack-oauth-callback"),
```

## Settings changes (`uptime_monitor/settings.py`)

```python
SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET", "")
```

## Template changes

Update `notification_settings.html` to add a "Connect Slack" button that links
to `{% url 'slack-oauth-initiate' %}`. Only show if `SLACK_CLIENT_ID` is configured
(pass as context from view).

## Files inventory

| Action | File |
|--------|------|
| Create | `notifications/backends/slack_backend.py` |
| Create | `notifications/views_slack.py` — OAuth initiate + callback |
| Modify | `notifications/dispatch.py` — register slack backend |
| Modify | `notifications/urls.py` — add 2 Slack OAuth routes |
| Modify | `notifications/templates/notifications/notification_settings.html` — add Slack button |
| Modify | `uptime_monitor/settings.py` — add `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET` |
| Modify | `notifications/tests.py` — add Slack tests |

## Tests (~9)

**Slack backend** (~3): correct payload/headers, raises on Slack API error,
skips when no token

**Slack OAuth** (~6): initiate redirects to Slack with correct params, callback
error param handled, state mismatch rejected, success creates channel, API
failure handled, login required

## Verification

```bash
python3 manage.py test notifications
python3 manage.py test monitors
```

Manual: set `SLACK_CLIENT_ID` and `SLACK_CLIENT_SECRET` env vars, click
"Connect Slack", complete OAuth flow, verify channel appears in settings,
trigger a notification and verify it posts to Slack.
