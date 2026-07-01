# Adding Twilio SMS alerts — the pragmatic path

This is the recommended order for adding SMS notifications (alongside the
existing Resend email alerts) without getting blocked on UK regulatory steps.

The idea: build and test the whole code path for **free** using Twilio's test
credentials, prove real delivery **once** with a trial number, and only then
deal with the production UK Sender ID registration.

## Prerequisites

- A Twilio account (the free trial is fine to start).
- The Twilio Python SDK: `pip install twilio` (add to `requirements.txt`).

## Step 1 — Build against Test Credentials + magic numbers (free, no real sends)

Twilio gives every account a **separate set of test credentials** that never
send a real message and are never charged.

1. In the Twilio Console, go to **Account → API keys & tokens** and copy the
   **Test Account SID** and **Test Auth Token** (these are distinct from your
   live credentials).
2. Point your code at them locally via env vars, e.g. in `.env`:
   ```
   TWILIO_ACCOUNT_SID=<Test Account SID>
   TWILIO_AUTH_TOKEN=<Test Auth Token>
   TWILIO_FROM_NUMBER=+15005550006
   ```
3. Use Twilio's **magic numbers** to force specific outcomes and confirm the
   code handles each:
   | Number | Simulated result |
   |--------|------------------|
   | `+15005550006` | Valid — request succeeds |
   | `+15005550001` | Invalid number → error 21211 |
   | `+15005550009` | SMS-incapable number → error 21407 |

   Use `+15005550006` as the `from` number and send to any of the above as the
   `to` number to exercise success and error paths.

**What this proves:** your integration builds the request correctly and handles
errors. **What it does not prove:** actual delivery — no real text is sent.

## Step 2 — One real send via a trial number (proves delivery)

1. Switch the env vars to your **live** Account SID / Auth Token.
2. In the Console, **verify your own mobile number** (trial accounts can only
   send to verified numbers).
3. Buy a trial phone number (or use the trial sending number) and send yourself
   one alert.
4. Confirm the text arrives. Trial messages include a
   "Sent from your Twilio trial account" prefix — that's expected.

**What this proves:** end-to-end delivery to a real handset.

## Step 3 — Production (UK Sender ID registration)

Only once Steps 1–2 pass, handle the production sender identity:

- **One-way alerts (recommended for this app):** register a UK **Alphanumeric
  Sender ID** (e.g. `UptimeMon`). This is a manual Console/regulatory step and
  requires business documents. Recipients cannot reply.
- **If you need replies / two-way:** buy a **UK mobile (+447) number** and
  clear the regulatory bundle (ID + proof of address).

> UK **geographic** (+44 20…, landline) and **toll-free** (+44 800) numbers
> cannot send SMS, so they are not options here.

## How this fits the codebase

Follow the same pattern as the existing Resend email integration:

- Add a Twilio sender to `monitors/notifications.py` next to
  `send_monitor_down_email` / `send_monitor_recovery_email`.
- Gate it on env vars (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_FROM_NUMBER`). When unset, **skip and log** — exactly how
  `RESEND_API_KEY` being empty is handled today.
- Read the vars in `uptime_monitor/settings.py` via `os.environ.get(...)`.
- Set the production values as Railway variables on the **web** and **worker**
  services (see `DEPLOY.md`); store secrets in the Bitwarden vault item.
