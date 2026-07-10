from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .models import NotificationChannel, NotificationPreference


# ---------------------------------------------------------------------------
# NotificationPreference model tests
# ---------------------------------------------------------------------------


class NotificationPreferenceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    def test_str_contains_on(self):
        pref = NotificationPreference.objects.create(
            user=self.user, category="test", label="Test", enabled=True,
        )
        self.assertIn("on", str(pref))

    def test_str_contains_off(self):
        pref = NotificationPreference.objects.create(
            user=self.user, category="test", label="Test", enabled=False,
        )
        self.assertIn("off", str(pref))

    def test_unique_together_enforced(self):
        NotificationPreference.objects.create(
            user=self.user, category="test", label="Test",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationPreference.objects.create(
                    user=self.user, category="test", label="Test2",
                )

    def test_default_enabled_true(self):
        pref = NotificationPreference.objects.create(
            user=self.user, category="test", label="Test",
        )
        self.assertTrue(pref.enabled)


# ---------------------------------------------------------------------------
# NotificationChannel model tests
# ---------------------------------------------------------------------------


class NotificationChannelModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    def test_create_webhook_channel(self):
        ch = NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="My Hook",
            webhook_url="https://example.com/hook",
        )
        self.assertEqual(ch.channel_type, "webhook")
        self.assertEqual(ch.webhook_url, "https://example.com/hook")

    def test_str_repr(self):
        ch = NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="My Hook",
        )
        s = str(ch)
        self.assertIn("alice", s)
        self.assertIn("Webhook", s)
        self.assertIn("My Hook", s)

    def test_default_enabled(self):
        ch = NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.SMS,
            label="Phone",
        )
        self.assertTrue(ch.enabled)

    def test_cascade_delete(self):
        NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Hook",
        )
        self.assertEqual(NotificationChannel.objects.count(), 1)
        self.user.delete()
        self.assertEqual(NotificationChannel.objects.count(), 0)

    def test_channel_types(self):
        types = dict(NotificationChannel.ChannelType.choices)
        self.assertIn("webhook", types)
        self.assertIn("slack", types)
        self.assertIn("sms", types)


# ---------------------------------------------------------------------------
# Email backend tests (send_email_backend — no preference logic)
# ---------------------------------------------------------------------------


@override_settings(RESEND_API_KEY="test-key", DEFAULT_FROM_EMAIL="test@example.com")
class SendEmailBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("notifications.email.resend.Emails.send")
    def test_sends_with_correct_payload(self, mock_send):
        from .email import send_email_backend
        send_email_backend(self.user, "Test Subject", "Test body")
        mock_send.assert_called_once()
        payload = mock_send.call_args.args[0]
        self.assertEqual(payload["to"], ["alice@test.com"])
        self.assertEqual(payload["subject"], "Test Subject")
        self.assertEqual(payload["text"], "Test body")
        self.assertEqual(payload["from"], "test@example.com")

    @override_settings(RESEND_API_KEY="")
    @patch("notifications.email.resend.Emails.send")
    def test_skips_when_api_key_empty(self, mock_send):
        from .email import send_email_backend
        send_email_backend(self.user, "Hi", "Body")
        mock_send.assert_not_called()

    @patch("notifications.email.resend.Emails.send")
    def test_skips_when_no_email(self, mock_send):
        no_email_user = User.objects.create_user("noemail", "", "pass1234")
        from .email import send_email_backend
        send_email_backend(no_email_user, "Hi", "Body")
        mock_send.assert_not_called()

    @patch("notifications.email.resend.Emails.send", side_effect=Exception("API error"))
    def test_exception_logged_not_raised(self, mock_send):
        from .email import send_email_backend
        send_email_backend(self.user, "Hi", "Body")


# ---------------------------------------------------------------------------
# send_email backward-compat wrapper tests
# ---------------------------------------------------------------------------


@override_settings(RESEND_API_KEY="test-key", DEFAULT_FROM_EMAIL="test@example.com")
class SendEmailWrapperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("notifications.email.resend.Emails.send")
    def test_sends_via_dispatch(self, mock_send):
        from .email import send_email
        send_email(
            user=self.user,
            subject="Test Subject",
            body="Test body",
            category="test_cat",
            category_label="Test Cat",
        )
        mock_send.assert_called_once()

    @patch("notifications.email.resend.Emails.send")
    def test_creates_preference_on_first_send(self, mock_send):
        from .email import send_email
        self.assertEqual(NotificationPreference.objects.count(), 0)
        send_email(
            user=self.user,
            subject="Hi",
            body="Body",
            category="new_cat",
            category_label="New Cat",
        )
        pref = NotificationPreference.objects.get(user=self.user, category="new_cat")
        self.assertTrue(pref.enabled)
        self.assertEqual(pref.label, "New Cat")

    @patch("notifications.email.resend.Emails.send")
    def test_skips_send_when_preference_disabled(self, mock_send):
        NotificationPreference.objects.create(
            user=self.user, category="off_cat", label="Off", enabled=False,
        )
        from .email import send_email
        send_email(
            user=self.user,
            subject="Hi",
            body="Body",
            category="off_cat",
        )
        mock_send.assert_not_called()

    @patch("notifications.email.resend.Emails.send")
    def test_no_category_no_preference_created(self, mock_send):
        from .email import send_email
        send_email(user=self.user, subject="Hi", body="Body")
        self.assertEqual(NotificationPreference.objects.count(), 0)
        mock_send.assert_called_once()

    @patch("notifications.email.resend.Emails.send")
    def test_existing_preference_not_overwritten(self, mock_send):
        NotificationPreference.objects.create(
            user=self.user, category="existing", label="Original Label", enabled=True,
        )
        from .email import send_email
        send_email(
            user=self.user,
            subject="Hi",
            body="Body",
            category="existing",
            category_label="New Label",
        )
        pref = NotificationPreference.objects.get(user=self.user, category="existing")
        self.assertEqual(pref.label, "Original Label")


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


@override_settings(RESEND_API_KEY="test-key", DEFAULT_FROM_EMAIL="test@example.com")
class DispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("notifications.email.resend.Emails.send")
    def test_email_only_when_no_channels(self, mock_send):
        from .dispatch import send_notification
        send_notification(self.user, "Sub", "Body")
        mock_send.assert_called_once()

    @patch("notifications.backends.webhook_backend.requests.post")
    @patch("notifications.email.resend.Emails.send")
    def test_sends_to_all_enabled_channels(self, mock_email, mock_webhook):
        mock_webhook.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Hook",
            webhook_url="https://example.com/hook",
            enabled=True,
        )
        from .dispatch import BACKENDS, send_notification
        BACKENDS.clear()
        send_notification(self.user, "Sub", "Body")
        mock_email.assert_called_once()
        mock_webhook.assert_called_once()

    @patch("notifications.backends.webhook_backend.requests.post")
    @patch("notifications.email.resend.Emails.send")
    def test_skips_disabled_channels(self, mock_email, mock_webhook):
        NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Hook",
            webhook_url="https://example.com/hook",
            enabled=False,
        )
        from .dispatch import BACKENDS, send_notification
        BACKENDS.clear()
        send_notification(self.user, "Sub", "Body")
        mock_email.assert_called_once()
        mock_webhook.assert_not_called()

    @patch("notifications.email.resend.Emails.send")
    def test_category_disabled_skips_everything(self, mock_email):
        NotificationPreference.objects.create(
            user=self.user, category="test_cat", label="Test", enabled=False,
        )
        NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Hook",
            webhook_url="https://example.com/hook",
            enabled=True,
        )
        from .dispatch import send_notification
        send_notification(self.user, "Sub", "Body", category="test_cat")
        mock_email.assert_not_called()

    @patch("notifications.backends.webhook_backend.requests.post", side_effect=Exception("fail"))
    @patch("notifications.email.resend.Emails.send")
    def test_backend_failure_doesnt_block_others(self, mock_email, mock_webhook):
        NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Hook",
            webhook_url="https://example.com/hook",
            enabled=True,
        )
        from .dispatch import BACKENDS, send_notification
        BACKENDS.clear()
        # Should not raise
        send_notification(self.user, "Sub", "Body")
        mock_email.assert_called_once()

    @patch("notifications.email.resend.Emails.send")
    def test_no_category_sends_to_all(self, mock_email):
        from .dispatch import send_notification
        send_notification(self.user, "Sub", "Body")
        mock_email.assert_called_once()


# ---------------------------------------------------------------------------
# Webhook backend tests
# ---------------------------------------------------------------------------


class WebhookBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("notifications.backends.webhook_backend.requests.post")
    def test_correct_payload(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        ch = NotificationChannel(
            webhook_url="https://example.com/hook",
            webhook_secret="",
        )
        from .backends.webhook_backend import send
        send(ch, "Alert", "Body text")
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"], {"subject": "Alert", "body": "Body text"})
        self.assertNotIn("X-Webhook-Secret", kwargs["headers"])

    @patch("notifications.backends.webhook_backend.requests.post")
    def test_secret_header_included(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        ch = NotificationChannel(
            webhook_url="https://example.com/hook",
            webhook_secret="s3cret",
        )
        from .backends.webhook_backend import send
        send(ch, "Alert", "Body")
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Webhook-Secret"], "s3cret")

    @patch("notifications.backends.webhook_backend.requests.post")
    def test_no_header_when_blank(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        ch = NotificationChannel(webhook_url="https://example.com/hook", webhook_secret="")
        from .backends.webhook_backend import send
        send(ch, "Alert", "Body")
        headers = mock_post.call_args.kwargs["headers"]
        self.assertNotIn("X-Webhook-Secret", headers)

    @patch("notifications.backends.webhook_backend.requests.post")
    def test_raises_on_http_error(self, mock_post):
        from requests.exceptions import HTTPError
        mock_post.return_value = MagicMock(raise_for_status=MagicMock(side_effect=HTTPError("500")))
        ch = NotificationChannel(webhook_url="https://example.com/hook", webhook_secret="")
        from .backends.webhook_backend import send
        with self.assertRaises(HTTPError):
            send(ch, "Alert", "Body")


class PushRelayBackendTests(TestCase):
    @override_settings(PUSH_RELAY_URL="https://push.example.com", PUSH_RELAY_SEND_KEY="k")
    @patch("notifications.backends.push_relay_backend.requests.post")
    def test_posts_to_send_api(self, mock_post):
        mock_post.return_value = MagicMock(status_code=202, raise_for_status=lambda: None)
        ch = NotificationChannel(push_relay_label="bilal")
        from .backends.push_relay_backend import send
        send(ch, "Alert", "Body text", url="https://uptime.example/monitors/5/")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://push.example.com/api/v1/send")
        self.assertEqual(
            kwargs["json"],
            {
                "label": "bilal",
                "notification": {
                    "title": "Alert",
                    "body": "Body text",
                    "url": "https://uptime.example/monitors/5/",
                },
            },
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer k")

    @override_settings(PUSH_RELAY_URL="", PUSH_RELAY_SEND_KEY="")
    @patch("notifications.backends.push_relay_backend.requests.post")
    def test_noop_when_unconfigured(self, mock_post):
        ch = NotificationChannel(push_relay_label="bilal")
        from .backends.push_relay_backend import send
        send(ch, "Alert", "Body")
        mock_post.assert_not_called()

    @patch("notifications.backends.push_relay_backend.requests.post")
    def test_noop_without_label(self, mock_post):
        ch = NotificationChannel(push_relay_label="")
        from .backends.push_relay_backend import send
        send(ch, "Alert", "Body")
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Notification settings view tests
# ---------------------------------------------------------------------------


MOCK_CATEGORIES = [
    ("cat_a", "Category A"),
    ("cat_b", "Category B"),
    ("cat_c", "Category C"),
]


@override_settings(NOTIFICATION_CATEGORIES=MOCK_CATEGORIES)
class NotificationSettingsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")

    def test_login_required(self):
        from django.test import Client
        c = Client()
        response = c.get("/settings/notifications/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_creates_missing_preferences(self):
        self.assertEqual(NotificationPreference.objects.count(), 0)
        self.client.get("/settings/notifications/")
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 3,
        )

    def test_get_doesnt_duplicate_existing(self):
        NotificationPreference.objects.create(
            user=self.user, category="cat_a", label="Category A",
        )
        self.client.get("/settings/notifications/")
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 3,
        )

    def test_post_enables_selected_disables_unselected(self):
        self.client.get("/settings/notifications/")
        prefs = list(NotificationPreference.objects.filter(user=self.user).order_by("category"))
        self.client.post("/settings/notifications/", {"enabled": [str(prefs[0].id)]})
        prefs[0].refresh_from_db()
        prefs[1].refresh_from_db()
        prefs[2].refresh_from_db()
        self.assertTrue(prefs[0].enabled)
        self.assertFalse(prefs[1].enabled)
        self.assertFalse(prefs[2].enabled)

    def test_post_nothing_checked_disables_all(self):
        self.client.get("/settings/notifications/")
        self.client.post("/settings/notifications/", {})
        for pref in NotificationPreference.objects.filter(user=self.user):
            self.assertFalse(pref.enabled)

    def test_post_redirects_with_success_message(self):
        self.client.get("/settings/notifications/")
        response = self.client.post("/settings/notifications/", {}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "updated")

    def test_channels_listed(self):
        NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="My Hook",
            webhook_url="https://example.com/hook",
        )
        response = self.client.get("/settings/notifications/")
        self.assertContains(response, "My Hook")

    def test_old_url_redirects(self):
        response = self.client.get("/settings/emails/")
        self.assertRedirects(response, "/settings/notifications/")


# ---------------------------------------------------------------------------
# Add webhook view tests
# ---------------------------------------------------------------------------


class AddWebhookViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")

    def test_login_required(self):
        from django.test import Client
        c = Client()
        response = c.get("/settings/notifications/add-webhook/")
        self.assertEqual(response.status_code, 302)

    def test_get_renders_form(self):
        response = self.client.get("/settings/notifications/add-webhook/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add Webhook")

    def test_valid_post_creates_channel(self):
        response = self.client.post("/settings/notifications/add-webhook/", {
            "label": "Test Hook",
            "webhook_url": "https://example.com/hook",
            "webhook_secret": "secret123",
        })
        self.assertRedirects(response, "/settings/notifications/")
        ch = NotificationChannel.objects.get(user=self.user)
        self.assertEqual(ch.channel_type, "webhook")
        self.assertEqual(ch.label, "Test Hook")
        self.assertEqual(ch.webhook_url, "https://example.com/hook")
        self.assertEqual(ch.webhook_secret, "secret123")

    def test_invalid_post_shows_errors(self):
        response = self.client.post("/settings/notifications/add-webhook/", {
            "label": "",
            "webhook_url": "not-a-url",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NotificationChannel.objects.count(), 0)


# ---------------------------------------------------------------------------
# Toggle / delete channel view tests
# ---------------------------------------------------------------------------


class ChannelCrudViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.channel = NotificationChannel.objects.create(
            user=self.user,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Hook",
            webhook_url="https://example.com/hook",
            enabled=True,
        )

    def test_toggle_disables(self):
        self.client.post(f"/settings/notifications/channels/{self.channel.id}/toggle/")
        self.channel.refresh_from_db()
        self.assertFalse(self.channel.enabled)

    def test_toggle_enables(self):
        self.channel.enabled = False
        self.channel.save()
        self.client.post(f"/settings/notifications/channels/{self.channel.id}/toggle/")
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.enabled)

    def test_delete_removes_channel(self):
        self.client.post(f"/settings/notifications/channels/{self.channel.id}/delete/")
        self.assertEqual(NotificationChannel.objects.count(), 0)

    def test_other_user_404(self):
        other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        other_ch = NotificationChannel.objects.create(
            user=other,
            channel_type=NotificationChannel.ChannelType.WEBHOOK,
            label="Bob Hook",
        )
        response = self.client.post(f"/settings/notifications/channels/{other_ch.id}/toggle/")
        self.assertEqual(response.status_code, 404)
        response = self.client.post(f"/settings/notifications/channels/{other_ch.id}/delete/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Slack backend tests
# ---------------------------------------------------------------------------


class SlackBackendTests(TestCase):
    @patch("notifications.backends.slack_backend.requests.post")
    def test_correct_payload_and_headers(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True})
        ch = NotificationChannel(
            slack_access_token="xoxb-test-token",
            slack_channel_id="C12345",
        )
        from .backends.slack_backend import send
        send(ch, "Alert", "Body text")
        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["json"]["channel"], "C12345")
        self.assertIn("Alert", kwargs["json"]["text"])
        self.assertIn("Bearer xoxb-test-token", kwargs["headers"]["Authorization"])

    @patch("notifications.backends.slack_backend.requests.post")
    def test_raises_on_slack_api_error(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": False, "error": "channel_not_found"})
        ch = NotificationChannel(
            slack_access_token="xoxb-test-token",
            slack_channel_id="C12345",
        )
        from .backends.slack_backend import send
        with self.assertRaises(RuntimeError):
            send(ch, "Alert", "Body")

    def test_skips_when_no_token(self):
        ch = NotificationChannel(slack_access_token="", slack_channel_id="C12345")
        from .backends.slack_backend import send
        # Should not raise or make requests
        send(ch, "Alert", "Body")


# ---------------------------------------------------------------------------
# Slack OAuth view tests
# ---------------------------------------------------------------------------


@override_settings(SLACK_CLIENT_ID="test-client-id", SLACK_CLIENT_SECRET="test-secret")
class SlackOAuthViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")

    def test_initiate_redirects_to_slack(self):
        response = self.client.get("/settings/notifications/slack/connect/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("slack.com/oauth/v2/authorize", response.url)
        self.assertIn("test-client-id", response.url)

    def test_callback_error_param_handled(self):
        response = self.client.get("/settings/notifications/slack/callback/?error=access_denied")
        self.assertRedirects(response, "/settings/notifications/")

    def test_callback_state_mismatch_rejected(self):
        session = self.client.session
        session["slack_oauth_state"] = "correct-state"
        session.save()
        response = self.client.get("/settings/notifications/slack/callback/?state=wrong-state&code=abc")
        self.assertRedirects(response, "/settings/notifications/")

    @patch("notifications.views_slack.requests.post")
    def test_callback_success_creates_channel(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {
            "ok": True,
            "access_token": "xoxb-new-token",
            "team": {"name": "Test Team"},
            "incoming_webhook": {
                "channel_id": "C99999",
                "channel": "general",
            },
        })
        session = self.client.session
        session["slack_oauth_state"] = "valid-state"
        session.save()
        response = self.client.get(
            "/settings/notifications/slack/callback/?state=valid-state&code=test-code"
        )
        self.assertRedirects(response, "/settings/notifications/")
        ch = NotificationChannel.objects.get(user=self.user)
        self.assertEqual(ch.channel_type, "slack")
        self.assertEqual(ch.slack_access_token, "xoxb-new-token")
        self.assertEqual(ch.slack_channel_id, "C99999")
        self.assertEqual(ch.slack_team_name, "Test Team")

    @patch("notifications.views_slack.requests.post")
    def test_callback_api_failure_handled(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": False, "error": "invalid_code"})
        session = self.client.session
        session["slack_oauth_state"] = "valid-state"
        session.save()
        response = self.client.get(
            "/settings/notifications/slack/callback/?state=valid-state&code=bad-code"
        )
        self.assertRedirects(response, "/settings/notifications/")
        self.assertEqual(NotificationChannel.objects.count(), 0)

    def test_login_required(self):
        from django.test import Client
        c = Client()
        response = c.get("/settings/notifications/slack/connect/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)


# ---------------------------------------------------------------------------
# SMS backend tests
# ---------------------------------------------------------------------------


@override_settings(TWILIO_ACCOUNT_SID="ACtest", TWILIO_AUTH_TOKEN="authtest", TWILIO_FROM_NUMBER="+15551234567")
class SMSBackendTests(TestCase):
    @patch("twilio.rest.Client")
    def test_correct_twilio_call(self, MockClient):
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        ch = NotificationChannel(sms_phone_number="+441234567890")
        from .backends.sms_backend import send
        send(ch, "Alert", "Body")
        mock_client.messages.create.assert_called_once_with(
            to="+441234567890",
            from_="+15551234567",
            body="Alert\nBody",
        )

    @override_settings(TWILIO_ACCOUNT_SID="")
    def test_skips_when_no_account_sid(self):
        ch = NotificationChannel(sms_phone_number="+441234567890")
        from .backends.sms_backend import send
        # Should not raise
        send(ch, "Alert", "Body")

    @patch("twilio.rest.Client")
    def test_skips_when_no_phone_number(self, MockClient):
        ch = NotificationChannel(sms_phone_number="")
        from .backends.sms_backend import send
        send(ch, "Alert", "Body")
        MockClient.assert_not_called()

    @patch("twilio.rest.Client")
    def test_truncates_long_messages(self, MockClient):
        mock_client = MagicMock()
        MockClient.return_value = mock_client
        ch = NotificationChannel(sms_phone_number="+441234567890")
        from .backends.sms_backend import send
        long_body = "x" * 2000
        send(ch, "Alert", long_body)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        self.assertTrue(len(call_kwargs["body"]) <= 1600)
        self.assertTrue(call_kwargs["body"].endswith("..."))


# ---------------------------------------------------------------------------
# SMS view tests
# ---------------------------------------------------------------------------


class AddSMSViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")

    def test_login_required(self):
        from django.test import Client
        c = Client()
        response = c.get("/settings/notifications/add-sms/")
        self.assertEqual(response.status_code, 302)

    def test_get_renders_form(self):
        response = self.client.get("/settings/notifications/add-sms/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add SMS")

    def test_valid_post_creates_channel(self):
        response = self.client.post("/settings/notifications/add-sms/", {
            "label": "My Phone",
            "sms_phone_number": "+441234567890",
        })
        self.assertRedirects(response, "/settings/notifications/")
        ch = NotificationChannel.objects.get(user=self.user)
        self.assertEqual(ch.channel_type, "sms")
        self.assertEqual(ch.sms_phone_number, "+441234567890")
