# Notifications

The `notifications` app is a **generic, channel-based notification system**. It is
fully decoupled from `monitors`: callers hand it a `user`, a `subject`, a `body`,
and an optional preference `category`. The app decides *who* to deliver to (based
on per-user preferences) and *how* (email plus any channels the user has connected).

Monitor-specific wording lives in `monitors/notifications.py`; this app knows
nothing about monitors, uptime, or SSL.

## Concepts

| Concept | Where | Purpose |
| --- | --- | --- |
| **Category** | `NotificationPreference` | A *type* of event (e.g. `monitor_down`). Users can opt out per category. |
| **Email** | `email.py` | Always-on baseline delivery via [Resend](https://resend.com). Not a channel. |
| **Channel** | `NotificationChannel` + `backends/` | An *additional*, user-connected destination: Slack, Webhook, or SMS. |
| **Backend** | `backends/*.py` | A `send(channel, subject, body)` callable that performs the actual delivery for one channel type. |
| **Dispatch** | `dispatch.py` | The single entry point that ties categories, email, and channels together. |

## Entry point

Everything flows through one function:

```python
from notifications.dispatch import send_notification

send_notification(user, subject, body, category="monitor_down", category_label="Monitor goes down")
```

`monitors/notifications.py` provides thin wrappers (`send_monitor_added_email`,
`send_monitor_down_email`, `send_monitor_recovery_email`, `send_ssl_expiring_email`)
that build monitor-specific copy and call `send_notification`.

## High-level architecture

```mermaid
flowchart TD
    subgraph monitors["monitors app"]
        MN["monitors/notifications.py<br/>(builds subject + body)"]
    end

    subgraph notifications["notifications app"]
        D["dispatch.send_notification()"]
        PREF["NotificationPreference<br/>(per-category opt-in/out)"]
        EMAIL["email.send_email_backend()"]
        REG["BACKENDS registry<br/>(channel_type → send fn)"]
        CH["NotificationChannel<br/>(user's connected channels)"]

        subgraph backends["backends/"]
            WB["webhook_backend.send()"]
            SB["slack_backend.send()"]
            SMSB["sms_backend.send()"]
        end
    end

    subgraph external["External services"]
        RESEND["Resend (email)"]
        SLACK["Slack API"]
        HTTP["Webhook endpoint"]
        TWILIO["Twilio (SMS)"]
    end

    MN --> D
    D -->|"1. check preference"| PREF
    D -->|"2. always"| EMAIL --> RESEND
    D -->|"3. each enabled channel"| REG
    REG --> CH
    REG --> WB --> HTTP
    REG --> SB --> SLACK
    REG --> SMSB --> TWILIO
```

## Dispatch flow

`send_notification` runs three steps in order (`dispatch.py`):

```mermaid
flowchart TD
    START["send_notification(user, subject, body, category)"] --> HASCAT{category given?}
    HASCAT -->|yes| GETPREF["get_or_create NotificationPreference<br/>for (user, category)"]
    GETPREF --> ENABLED{preference<br/>enabled?}
    ENABLED -->|no| STOP["return — nothing sent"]
    ENABLED -->|yes| EMAIL
    HASCAT -->|no| EMAIL["send email (always)"]

    EMAIL --> LOADCH["load enabled NotificationChannels<br/>for this user"]
    LOADCH --> LOOP["for each channel"]
    LOOP --> LOOKUP["look up backend by channel_type"]
    LOOKUP --> FOUND{backend<br/>registered?}
    FOUND -->|no| WARN["log warning, skip"]
    FOUND -->|yes| SEND["backend(channel, subject, body)"]
    SEND --> OK{raised?}
    OK -->|no| NEXT["next channel"]
    OK -->|yes| CATCH["log via logger.exception<br/>(surfaces in Sentry)"]
    CATCH --> NEXT
    WARN --> NEXT
    NEXT --> LOOP
```

Key behaviours:

- **The category gate only guards email + channels together.** If the user
  disabled the category, nothing is sent at all.
- **Email is always attempted** (subject to the category gate). It is *not* a
  channel and has no on/off toggle beyond the category preference.
- **Channel failures are isolated.** Each backend call is wrapped in
  `try/except`; a failure is logged with `logger.exception(...)` and the loop
  continues to the next channel. Because Sentry's logging integration captures
  `ERROR`-level records, these handled failures still appear as Sentry issues
  (see the repo root [README](../README.md#error-tracking-sentry)).

## Data model

```mermaid
classDiagram
    class User {
        +email
    }
    class NotificationPreference {
        +category
        +label
        +enabled
    }
    class NotificationChannel {
        +channel_type  slack|webhook|sms
        +label
        +enabled
        +slack_access_token
        +slack_channel_id
        +webhook_url
        +webhook_secret
        +sms_phone_number
    }
    User "1" --> "*" NotificationPreference : preferences
    User "1" --> "*" NotificationChannel : channels
```

- `NotificationPreference` is unique per `(user, category)`. Categories are
  declared in `settings.NOTIFICATION_CATEGORIES` and created lazily on first use.
- `NotificationChannel` is a single table holding config for **all** channel
  types; only the fields relevant to `channel_type` are populated.

## The backend registry

Backends are registered lazily in `dispatch._register_backends()` so that
importing the app never eagerly imports `requests`, the Slack code, or the Twilio
SDK:

```python
BACKENDS = {
    ChannelType.WEBHOOK: webhook_backend.send,
    ChannelType.SLACK:   slack_backend.send,
    ChannelType.SMS:     sms_backend.send,
}
```

Every backend implements the same contract:

```python
def send(channel, subject, body):
    ...  # raise on failure; dispatch will catch and log
```

Each backend **short-circuits (returns silently) when its channel is not fully
configured**, and **raises on a real delivery failure** so dispatch can log it.

## Channels

### Email (baseline, not a channel)

- **File:** `email.py` · **Provider:** Resend
- Always attempted for every notification (subject to the category gate).
- Skipped with a warning if `RESEND_API_KEY` is unset or the user has no email.
- Swallows its own exceptions internally (logs, does not re-raise).

### Webhook

- **File:** `backends/webhook_backend.py` · **Setup:** `add_webhook_channel_view`
- POSTs JSON `{"subject", "body"}` to `channel.webhook_url`.
- Optional `webhook_secret` is sent as the `X-Webhook-Secret` header.
- Calls `response.raise_for_status()` — any non-2xx raises.

```mermaid
sequenceDiagram
    participant U as User
    participant V as add_webhook_channel_view
    participant DB as NotificationChannel
    U->>V: POST label + webhook_url + secret
    V->>DB: create channel (type=webhook)
    Note over DB: later, on an event…
    DB-->>U: POST {subject, body} to webhook_url<br/>(+ X-Webhook-Secret)
```

### Slack

- **Files:** `views_slack.py` (OAuth), `backends/slack_backend.py` (send)
- Connected via **Slack OAuth v2**, not a manual form. The user authorizes the
  app; the callback stores the bot `access_token`, `channel_id`, and channel/team
  names on a new `NotificationChannel`.
- Sends via `chat.postMessage`. Slack returns HTTP 200 even on logical errors, so
  the backend inspects `data["ok"]` and raises `RuntimeError` with the Slack
  error code (e.g. `not_in_channel` if the bot was never invited to the channel).

```mermaid
sequenceDiagram
    participant U as User
    participant I as slack_oauth_initiate
    participant S as Slack
    participant C as slack_oauth_callback
    participant DB as NotificationChannel
    participant B as slack_backend.send

    U->>I: click "Connect Slack"
    I->>I: store CSRF state in session
    I->>S: redirect to authorize (scope=chat:write,incoming-webhook)
    S->>U: user approves
    S->>C: redirect back with code + state
    C->>C: verify state matches session
    C->>S: POST oauth.v2.access (exchange code)
    S-->>C: access_token, channel_id, team
    C->>DB: create channel (type=slack)

    Note over DB: later, on an event…
    B->>S: chat.postMessage(channel_id, text)
    S-->>B: 200 {ok: false, error: "not_in_channel"}
    B->>B: raise RuntimeError(error)
```

### SMS

- **File:** `backends/sms_backend.py` · **Setup:** `add_sms_channel_view` · **Provider:** Twilio
- User enters a phone number in **E.164** format (e.g. `+441234567890`).
- Requires `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER`
  settings; the "add SMS" UI is only offered when Twilio is configured.
- Truncates the message to Twilio's 1600-char limit.
- Twilio validates the destination server-side and raises
  `TwilioRestException` (HTTP 400) for an invalid `To` number.

## Managing channels (UI)

All channel management lives under `/settings/notifications/` (`urls.py`):

| Action | URL name | View |
| --- | --- | --- |
| View settings + list channels | `notification-settings` | `notification_settings_view` |
| Add webhook | `add-webhook-channel` | `add_webhook_channel_view` |
| Add SMS | `add-sms-channel` | `add_sms_channel_view` |
| Connect Slack (OAuth) | `slack-oauth-initiate` → `slack-oauth-callback` | `views_slack.*` |
| Enable/disable a channel | `toggle-channel` | `toggle_channel_view` |
| Delete a channel | `delete-channel` | `delete_channel_view` |

```mermaid
stateDiagram-v2
    [*] --> Added : add / connect
    Added --> Enabled
    Enabled --> Disabled : toggle
    Disabled --> Enabled : toggle
    Enabled --> [*] : delete
    Disabled --> [*] : delete
    note right of Disabled
        Disabled channels are
        skipped by dispatch
        (filter enabled=True)
    end note
```

Toggle and delete are owner-scoped (`get_object_or_404(..., user=request.user)`)
and require POST.

## Relevant settings

```python
# uptime_monitor/settings.py
NOTIFICATION_CATEGORIES = [...]     # (category, label) pairs

RESEND_API_KEY / DEFAULT_FROM_EMAIL # email
SLACK_CLIENT_ID / SLACK_CLIENT_SECRET
TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER
```
