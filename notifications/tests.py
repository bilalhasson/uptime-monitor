from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .models import NotificationPreference


# ---------------------------------------------------------------------------
# Model tests
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
# Email sending tests
# ---------------------------------------------------------------------------


@override_settings(RESEND_API_KEY="test-key", DEFAULT_FROM_EMAIL="test@example.com")
class SendEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("notifications.email.resend.Emails.send")
    def test_sends_with_correct_payload(self, mock_send):
        from .email import send_email
        send_email(
            user=self.user,
            subject="Test Subject",
            body="Test body",
            category="test_cat",
            category_label="Test Cat",
        )
        mock_send.assert_called_once()
        payload = mock_send.call_args.args[0]
        self.assertEqual(payload["to"], ["alice@test.com"])
        self.assertEqual(payload["subject"], "Test Subject")
        self.assertEqual(payload["text"], "Test body")
        self.assertEqual(payload["from"], "test@example.com")

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

    @override_settings(RESEND_API_KEY="")
    @patch("notifications.email.resend.Emails.send")
    def test_skips_send_when_api_key_empty(self, mock_send):
        from .email import send_email
        send_email(user=self.user, subject="Hi", body="Body")
        mock_send.assert_not_called()

    @patch("notifications.email.resend.Emails.send")
    def test_skips_send_when_no_email(self, mock_send):
        no_email_user = User.objects.create_user("noemail", "", "pass1234")
        from .email import send_email
        send_email(user=no_email_user, subject="Hi", body="Body")
        mock_send.assert_not_called()

    @patch("notifications.email.resend.Emails.send", side_effect=Exception("API error"))
    def test_resend_exception_logged_not_raised(self, mock_send):
        from .email import send_email
        # Should not raise
        send_email(user=self.user, subject="Hi", body="Body")

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
# Preferences view tests
# ---------------------------------------------------------------------------


MOCK_CATEGORIES = [
    ("cat_a", "Category A"),
    ("cat_b", "Category B"),
    ("cat_c", "Category C"),
]


@override_settings(NOTIFICATION_CATEGORIES=MOCK_CATEGORIES)
class EmailPreferencesViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")

    def test_login_required(self):
        from django.test import Client
        c = Client()
        response = c.get("/settings/emails/")
        self.assertEqual(response.status_code, 302)

    def test_get_creates_missing_preferences(self):
        self.assertEqual(NotificationPreference.objects.count(), 0)
        self.client.get("/settings/emails/")
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 3,
        )

    def test_get_doesnt_duplicate_existing(self):
        NotificationPreference.objects.create(
            user=self.user, category="cat_a", label="Category A",
        )
        self.client.get("/settings/emails/")
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 3,
        )

    def test_post_enables_selected_disables_unselected(self):
        self.client.get("/settings/emails/")  # create prefs
        prefs = list(NotificationPreference.objects.filter(user=self.user).order_by("category"))
        # Enable only the first one
        self.client.post("/settings/emails/", {"enabled": [str(prefs[0].id)]})
        prefs[0].refresh_from_db()
        prefs[1].refresh_from_db()
        prefs[2].refresh_from_db()
        self.assertTrue(prefs[0].enabled)
        self.assertFalse(prefs[1].enabled)
        self.assertFalse(prefs[2].enabled)

    def test_post_nothing_checked_disables_all(self):
        self.client.get("/settings/emails/")  # create prefs
        self.client.post("/settings/emails/", {})
        for pref in NotificationPreference.objects.filter(user=self.user):
            self.assertFalse(pref.enabled)

    def test_post_redirects_with_success_message(self):
        self.client.get("/settings/emails/")  # create prefs
        response = self.client.post("/settings/emails/", {})
        self.assertRedirects(response, "/settings/emails/")
        # Follow redirect and check for message
        response = self.client.get("/settings/emails/")
        messages = list(response.context["messages"])
        self.assertTrue(any("updated" in str(m).lower() for m in messages))
