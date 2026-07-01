from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from .forms import MonitorForm, SignupForm
from .models import CheckLog, Monitor


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class MonitorModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_str_returns_url(self):
        self.assertEqual(str(self.monitor), "https://example.com")

    def test_default_status_is_pending(self):
        self.assertEqual(self.monitor.current_status, Monitor.Status.PENDING)

    def test_default_interval_is_300(self):
        self.assertEqual(self.monitor.check_interval, 300)

    def test_default_is_paused_false(self):
        self.assertFalse(self.monitor.is_paused)

    def test_default_last_checked_at_none(self):
        self.assertIsNone(self.monitor.last_checked_at)

    def test_created_at_set(self):
        self.assertIsNotNone(self.monitor.created_at)

    def test_cascade_deletes_checklogs(self):
        CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        self.assertEqual(CheckLog.objects.count(), 1)
        self.monitor.delete()
        self.assertEqual(CheckLog.objects.count(), 0)


class CheckLogModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_str_contains_ok(self):
        log = CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        self.assertIn("OK", str(log))

    def test_str_contains_fail(self):
        log = CheckLog.objects.create(monitor=self.monitor, success=False, status_code=500)
        self.assertIn("FAIL", str(log))

    def test_ordering_newest_first(self):
        log1 = CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        log2 = CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        logs = list(CheckLog.objects.all())
        self.assertEqual(logs[0].pk, log2.pk)
        self.assertEqual(logs[1].pk, log1.pk)

    def test_reverse_relation_check_logs(self):
        CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        self.assertEqual(self.monitor.check_logs.count(), 1)


# ---------------------------------------------------------------------------
# Form tests
# ---------------------------------------------------------------------------


class SignupFormTests(TestCase):
    def test_valid_form_creates_user(self):
        form = SignupForm(data={
            "username": "newuser",
            "email": "new@test.com",
            "password1": "strongpass123!",
            "password2": "strongpass123!",
        })
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, "newuser")

    def test_password_mismatch_invalid(self):
        form = SignupForm(data={
            "username": "newuser",
            "email": "new@test.com",
            "password1": "strongpass123!",
            "password2": "differentpass123!",
        })
        self.assertFalse(form.is_valid())


class MonitorFormTests(TestCase):
    def test_valid_data_accepted(self):
        form = MonitorForm(data={"url": "https://example.com", "check_interval": 300})
        self.assertTrue(form.is_valid())

    def test_url_required(self):
        form = MonitorForm(data={"check_interval": 300})
        self.assertFalse(form.is_valid())
        self.assertIn("url", form.errors)

    def test_invalid_url_rejected(self):
        form = MonitorForm(data={"url": "not-a-url", "check_interval": 300})
        self.assertFalse(form.is_valid())

    def test_only_url_and_check_interval_exposed(self):
        self.assertEqual(list(MonitorForm.Meta.fields), ["url", "check_interval"])


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------


class SignupViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get("/accounts/signup/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_valid_post_creates_user_and_logs_in(self):
        response = self.client.post("/accounts/signup/", {
            "username": "newuser",
            "email": "new@test.com",
            "password1": "strongpass123!",
            "password2": "strongpass123!",
        })
        self.assertRedirects(response, "/")
        self.assertTrue(User.objects.filter(username="newuser").exists())
        # User should be logged in (session has _auth_user_id)
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_post_rerenders(self):
        response = self.client.post("/accounts/signup/", {
            "username": "",
            "password1": "a",
            "password2": "b",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://alice.com")
        Monitor.objects.create(owner=self.other, url="https://bob.com")

    def test_login_required(self):
        c = Client()
        response = c.get("/")
        self.assertEqual(response.status_code, 302)

    def test_get_lists_own_monitors_only(self):
        response = self.client.get("/")
        monitors = list(response.context["monitors"])
        self.assertEqual(len(monitors), 1)
        self.assertEqual(monitors[0].url, "https://alice.com")

    @patch("monitors.views.send_monitor_added_email")
    def test_post_creates_monitor_and_sends_email(self, mock_email):
        response = self.client.post("/", {
            "url": "https://new-site.com",
            "check_interval": 60,
        })
        self.assertRedirects(response, "/")
        self.assertTrue(Monitor.objects.filter(url="https://new-site.com").exists())
        mock_email.assert_called_once()

    def test_invalid_post_rerenders(self):
        response = self.client.post("/", {"url": "", "check_interval": 300})
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)


class MonitorDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_login_required(self):
        c = Client()
        response = c.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_owner_can_view(self):
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_non_owner_gets_404(self):
        self.client.login(username="bob", password="pass1234")
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_no_checks_uptime_none(self):
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertIsNone(response.context["uptime_pct"])

    def test_uptime_pct_calculation(self):
        for success in [True, True, True, False]:
            CheckLog.objects.create(
                monitor=self.monitor, success=success, status_code=200 if success else 500,
            )
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.context["uptime_pct"], 75.0)

    def test_avg_response_time_calculation(self):
        CheckLog.objects.create(
            monitor=self.monitor, success=True, status_code=200, response_time_ms=100,
        )
        CheckLog.objects.create(
            monitor=self.monitor, success=True, status_code=200, response_time_ms=200,
        )
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.context["avg_response_time"], 150)

    def test_null_response_times_skipped_in_avg(self):
        CheckLog.objects.create(
            monitor=self.monitor, success=True, status_code=200, response_time_ms=100,
        )
        CheckLog.objects.create(
            monitor=self.monitor, success=False, response_time_ms=None,
        )
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.context["avg_response_time"], 100)

    def test_check_logs_capped_at_50(self):
        for i in range(55):
            CheckLog.objects.create(
                monitor=self.monitor, success=True, status_code=200,
            )
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(len(response.context["check_logs"]), 50)


class MonitorTogglePauseViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_login_required(self):
        c = Client()
        response = c.post(f"/monitors/{self.monitor.pk}/toggle-pause/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_get_returns_405(self):
        response = self.client.get(f"/monitors/{self.monitor.pk}/toggle-pause/")
        self.assertEqual(response.status_code, 405)

    def test_toggles_pause_on(self):
        self.assertFalse(self.monitor.is_paused)
        self.client.post(f"/monitors/{self.monitor.pk}/toggle-pause/")
        self.monitor.refresh_from_db()
        self.assertTrue(self.monitor.is_paused)

    def test_toggles_pause_off(self):
        self.monitor.is_paused = True
        self.monitor.save()
        self.client.post(f"/monitors/{self.monitor.pk}/toggle-pause/")
        self.monitor.refresh_from_db()
        self.assertFalse(self.monitor.is_paused)

    def test_non_owner_404(self):
        self.client.login(username="bob", password="pass1234")
        response = self.client.post(f"/monitors/{self.monitor.pk}/toggle-pause/")
        self.assertEqual(response.status_code, 404)

    def test_respects_next_param(self):
        response = self.client.post(
            f"/monitors/{self.monitor.pk}/toggle-pause/",
            {"next": f"/monitors/{self.monitor.pk}/"},
        )
        self.assertRedirects(response, f"/monitors/{self.monitor.pk}/")

    def test_defaults_redirect_to_root(self):
        response = self.client.post(f"/monitors/{self.monitor.pk}/toggle-pause/")
        self.assertRedirects(response, "/")


class MonitorEditViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.monitor = Monitor.objects.create(
            owner=self.user, url="https://example.com", check_interval=300,
        )

    def test_login_required(self):
        c = Client()
        response = c.get(f"/monitors/{self.monitor.pk}/edit/")
        self.assertEqual(response.status_code, 302)

    def test_get_prefills_form(self):
        response = self.client.get(f"/monitors/{self.monitor.pk}/edit/")
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["url"], "https://example.com")

    def test_non_owner_404(self):
        self.client.login(username="bob", password="pass1234")
        response = self.client.get(f"/monitors/{self.monitor.pk}/edit/")
        self.assertEqual(response.status_code, 404)

    def test_valid_post_updates_monitor(self):
        self.client.post(f"/monitors/{self.monitor.pk}/edit/", {
            "url": "https://updated.com",
            "check_interval": 60,
        })
        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.url, "https://updated.com")
        self.assertEqual(self.monitor.check_interval, 60)

    def test_invalid_post_rerenders(self):
        response = self.client.post(f"/monitors/{self.monitor.pk}/edit/", {
            "url": "",
            "check_interval": 300,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)


class MonitorDeleteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_login_required(self):
        c = Client()
        response = c.get(f"/monitors/{self.monitor.pk}/delete/")
        self.assertEqual(response.status_code, 302)

    def test_get_shows_confirmation(self):
        response = self.client.get(f"/monitors/{self.monitor.pk}/delete/")
        self.assertEqual(response.status_code, 200)

    def test_non_owner_404(self):
        self.client.login(username="bob", password="pass1234")
        response = self.client.get(f"/monitors/{self.monitor.pk}/delete/")
        self.assertEqual(response.status_code, 404)

    def test_post_deletes_and_redirects(self):
        response = self.client.post(f"/monitors/{self.monitor.pk}/delete/")
        self.assertRedirects(response, "/")
        self.assertFalse(Monitor.objects.filter(pk=self.monitor.pk).exists())


# ---------------------------------------------------------------------------
# Task tests
# ---------------------------------------------------------------------------


class CheckMonitorTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.monitor = Monitor.objects.create(
            owner=self.user, url="https://example.com", current_status=Monitor.Status.PENDING,
        )

    def _mock_response(self, status_code=200, elapsed=0.1):
        resp = MagicMock()
        resp.status_code = status_code
        return resp

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_successful_check(self, mock_get, mock_down, mock_recovery):
        mock_get.return_value = self._mock_response(200)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)
        self.assertIsNotNone(log.response_time_ms)

        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.current_status, Monitor.Status.UP)

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_failed_check_500(self, mock_get, mock_down, mock_recovery):
        mock_get.return_value = self._mock_response(500)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertFalse(log.success)
        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.current_status, Monitor.Status.DOWN)

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_399_is_success(self, mock_get, mock_down, mock_recovery):
        mock_get.return_value = self._mock_response(399)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertTrue(log.success)

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_400_is_failure(self, mock_get, mock_down, mock_recovery):
        mock_get.return_value = self._mock_response(400)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertFalse(log.success)

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_timeout_error(self, mock_get, mock_down, mock_recovery):
        import requests as req
        mock_get.side_effect = req.Timeout()
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "Request timed out")

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_connection_error(self, mock_get, mock_down, mock_recovery):
        import requests as req
        mock_get.side_effect = req.ConnectionError()
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertEqual(log.error_message, "Connection error")

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_too_many_redirects_error(self, mock_get, mock_down, mock_recovery):
        import requests as req
        mock_get.side_effect = req.TooManyRedirects()
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertEqual(log.error_message, "Too many redirects")

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_generic_request_exception_truncated(self, mock_get, mock_down, mock_recovery):
        import requests as req
        mock_get.side_effect = req.RequestException("x" * 300)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        log = CheckLog.objects.get()
        self.assertEqual(len(log.error_message), 255)

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_paused_monitor_skipped(self, mock_get, mock_down, mock_recovery):
        self.monitor.is_paused = True
        self.monitor.save()
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        self.assertEqual(CheckLog.objects.count(), 0)
        mock_get.assert_not_called()

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_nonexistent_monitor_returns_silently(self, mock_get, mock_down, mock_recovery):
        from .tasks import check_monitor
        check_monitor(99999)  # should not raise
        mock_get.assert_not_called()

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_up_to_down_sends_down_email(self, mock_get, mock_down, mock_recovery):
        self.monitor.current_status = Monitor.Status.UP
        self.monitor.save()
        mock_get.return_value = self._mock_response(500)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        mock_down.assert_called_once()
        mock_recovery.assert_not_called()

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_down_to_up_sends_recovery_email(self, mock_get, mock_down, mock_recovery):
        self.monitor.current_status = Monitor.Status.DOWN
        self.monitor.save()
        mock_get.return_value = self._mock_response(200)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        mock_recovery.assert_called_once()
        mock_down.assert_not_called()

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_pending_to_up_sends_nothing(self, mock_get, mock_down, mock_recovery):
        mock_get.return_value = self._mock_response(200)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        mock_down.assert_not_called()
        mock_recovery.assert_not_called()

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_pending_to_down_sends_nothing(self, mock_get, mock_down, mock_recovery):
        mock_get.return_value = self._mock_response(500)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        mock_down.assert_not_called()
        mock_recovery.assert_not_called()

    @patch("monitors.tasks.send_monitor_recovery_email")
    @patch("monitors.tasks.send_monitor_down_email")
    @patch("monitors.tasks.requests.get")
    def test_same_to_same_sends_nothing(self, mock_get, mock_down, mock_recovery):
        self.monitor.current_status = Monitor.Status.UP
        self.monitor.save()
        mock_get.return_value = self._mock_response(200)
        from .tasks import check_monitor
        check_monitor(self.monitor.pk)

        mock_down.assert_not_called()
        mock_recovery.assert_not_called()


class CheckAllMonitorsTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("monitors.tasks.check_monitor.delay")
    def test_calls_delay_for_unpaused_only(self, mock_delay):
        m1 = Monitor.objects.create(owner=self.user, url="https://a.com", is_paused=False)
        m2 = Monitor.objects.create(owner=self.user, url="https://b.com", is_paused=True)
        m3 = Monitor.objects.create(owner=self.user, url="https://c.com", is_paused=False)

        from .tasks import check_all_monitors
        check_all_monitors()

        called_ids = {call.args[0] for call in mock_delay.call_args_list}
        self.assertIn(m1.pk, called_ids)
        self.assertNotIn(m2.pk, called_ids)
        self.assertIn(m3.pk, called_ids)


# ---------------------------------------------------------------------------
# Notification helper tests
# ---------------------------------------------------------------------------


class MonitorNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    @patch("monitors.notifications.send_email")
    def test_send_monitor_added_email(self, mock_send):
        from .notifications import send_monitor_added_email
        send_monitor_added_email(self.monitor)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["category"], "monitor_added")
        self.assertIn("https://example.com", kwargs["subject"])

    @patch("monitors.notifications.send_email")
    def test_send_monitor_down_email(self, mock_send):
        from .notifications import send_monitor_down_email
        send_monitor_down_email(self.monitor)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["category"], "monitor_down")
        self.assertIn("DOWN", kwargs["subject"])

    @patch("monitors.notifications.send_email")
    def test_send_monitor_recovery_email(self, mock_send):
        from .notifications import send_monitor_recovery_email
        send_monitor_recovery_email(self.monitor)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["category"], "monitor_recovered")
        self.assertIn("UP", kwargs["subject"])


# ---------------------------------------------------------------------------
# SSL field tests
# ---------------------------------------------------------------------------


class SSLFieldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_default_ssl_fields_null_or_blank(self):
        self.assertIsNone(self.monitor.ssl_expiry_date)
        self.assertEqual(self.monitor.ssl_issuer, "")
        self.assertIsNone(self.monitor.ssl_last_checked_at)
        self.assertEqual(self.monitor.ssl_error, "")

    def test_ssl_expiry_notified_default_false(self):
        self.assertFalse(self.monitor.ssl_expiry_notified)

    def test_ssl_fields_stored_after_update(self):
        now = timezone.now()
        expiry = now + timedelta(days=30)
        self.monitor.ssl_expiry_date = expiry
        self.monitor.ssl_issuer = "Let's Encrypt"
        self.monitor.ssl_last_checked_at = now
        self.monitor.save()
        self.monitor.refresh_from_db()
        self.assertEqual(self.monitor.ssl_issuer, "Let's Encrypt")
        self.assertIsNotNone(self.monitor.ssl_expiry_date)
        self.assertIsNotNone(self.monitor.ssl_last_checked_at)


# ---------------------------------------------------------------------------
# SSL task tests
# ---------------------------------------------------------------------------


class SSLTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.monitor = Monitor.objects.create(
            owner=self.user, url="https://example.com",
        )

    def _make_cert(self, days_from_now=30, org="Test CA"):
        expiry = timezone.now() + timedelta(days=days_from_now)
        not_after = expiry.strftime("%b %d %H:%M:%S %Y GMT")
        return {
            "notAfter": not_after,
            "issuer": ((("organizationName", org),),),
        }

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_skips_non_https_monitor(self, mock_conn, mock_ctx, mock_email):
        self.monitor.url = "http://example.com"
        self.monitor.save()
        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)
        mock_conn.assert_not_called()

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_skips_paused_monitor(self, mock_conn, mock_ctx, mock_email):
        self.monitor.is_paused = True
        self.monitor.save()
        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)
        mock_conn.assert_not_called()

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_successful_check_stores_fields(self, mock_conn, mock_ctx, mock_email):
        cert = self._make_cert(days_from_now=60, org="Let's Encrypt")
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = cert
        mock_ssock.__enter__ = MagicMock(return_value=mock_ssock)
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value = mock_sock

        mock_ctx_instance = MagicMock()
        mock_ctx_instance.wrap_socket.return_value = mock_ssock
        mock_ctx.return_value = mock_ctx_instance

        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)

        self.monitor.refresh_from_db()
        self.assertIsNotNone(self.monitor.ssl_expiry_date)
        self.assertEqual(self.monitor.ssl_issuer, "Let's Encrypt")
        self.assertIsNotNone(self.monitor.ssl_last_checked_at)
        self.assertEqual(self.monitor.ssl_error, "")

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_connection_error_stores_ssl_error(self, mock_conn, mock_ctx, mock_email):
        import socket
        mock_conn.side_effect = socket.error("Connection refused")

        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)

        self.monitor.refresh_from_db()
        self.assertIn("Connection refused", self.monitor.ssl_error)
        self.assertIsNone(self.monitor.ssl_expiry_date)

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_sends_notification_when_expiring_soon(self, mock_conn, mock_ctx, mock_email):
        cert = self._make_cert(days_from_now=10)
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = cert
        mock_ssock.__enter__ = MagicMock(return_value=mock_ssock)
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value = mock_sock

        mock_ctx_instance = MagicMock()
        mock_ctx_instance.wrap_socket.return_value = mock_ssock
        mock_ctx.return_value = mock_ctx_instance

        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)

        mock_email.assert_called_once()
        self.monitor.refresh_from_db()
        self.assertTrue(self.monitor.ssl_expiry_notified)

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_does_not_renotify_when_already_notified(self, mock_conn, mock_ctx, mock_email):
        self.monitor.ssl_expiry_notified = True
        self.monitor.save()

        cert = self._make_cert(days_from_now=10)
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = cert
        mock_ssock.__enter__ = MagicMock(return_value=mock_ssock)
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value = mock_sock

        mock_ctx_instance = MagicMock()
        mock_ctx_instance.wrap_socket.return_value = mock_ssock
        mock_ctx.return_value = mock_ctx_instance

        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)

        mock_email.assert_not_called()

    @patch("monitors.tasks.send_ssl_expiring_email")
    @patch("monitors.tasks.ssl.create_default_context")
    @patch("monitors.tasks.socket.create_connection")
    def test_resets_flag_when_cert_renewed(self, mock_conn, mock_ctx, mock_email):
        old_expiry = timezone.now() + timedelta(days=5)
        self.monitor.ssl_expiry_date = old_expiry
        self.monitor.ssl_expiry_notified = True
        self.monitor.save()

        # New cert with a different (later) expiry
        cert = self._make_cert(days_from_now=90)
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = cert
        mock_ssock.__enter__ = MagicMock(return_value=mock_ssock)
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value = mock_sock

        mock_ctx_instance = MagicMock()
        mock_ctx_instance.wrap_socket.return_value = mock_ssock
        mock_ctx.return_value = mock_ctx_instance

        from .tasks import check_ssl_certificate
        check_ssl_certificate(self.monitor.pk)

        self.monitor.refresh_from_db()
        self.assertFalse(self.monitor.ssl_expiry_notified)


class CheckAllSSLCertificatesTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")

    @patch("monitors.tasks.check_ssl_certificate.delay")
    def test_queues_only_https_unpaused(self, mock_delay):
        m1 = Monitor.objects.create(owner=self.user, url="https://a.com", is_paused=False)
        m2 = Monitor.objects.create(owner=self.user, url="http://b.com", is_paused=False)
        m3 = Monitor.objects.create(owner=self.user, url="https://c.com", is_paused=True)
        m4 = Monitor.objects.create(owner=self.user, url="https://d.com", is_paused=False)

        from .tasks import check_all_ssl_certificates
        check_all_ssl_certificates()

        called_ids = {call.args[0] for call in mock_delay.call_args_list}
        self.assertIn(m1.pk, called_ids)
        self.assertNotIn(m2.pk, called_ids)
        self.assertNotIn(m3.pk, called_ids)
        self.assertIn(m4.pk, called_ids)


# ---------------------------------------------------------------------------
# SSL notification tests
# ---------------------------------------------------------------------------


class SSLNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")
        self.monitor.ssl_expiry_date = timezone.now() + timedelta(days=10)
        self.monitor.ssl_issuer = "Let's Encrypt"

    @patch("monitors.notifications.send_email")
    def test_send_ssl_expiring_email_calls_send_email(self, mock_send):
        from .notifications import send_ssl_expiring_email
        send_ssl_expiring_email(self.monitor, 10)

        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["category"], "ssl_expiring")
        self.assertIn("expiring soon", kwargs["subject"])

    @patch("monitors.notifications.send_email")
    def test_ssl_email_contains_days_and_url(self, mock_send):
        from .notifications import send_ssl_expiring_email
        send_ssl_expiring_email(self.monitor, 10)

        kwargs = mock_send.call_args.kwargs
        self.assertIn("10 days", kwargs["body"])
        self.assertIn("https://example.com", kwargs["body"])


# ---------------------------------------------------------------------------
# SSL detail view tests
# ---------------------------------------------------------------------------


class SSLDetailViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.client.login(username="alice", password="pass1234")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_detail_shows_ssl_info_for_https(self):
        self.monitor.ssl_expiry_date = timezone.now() + timedelta(days=30)
        self.monitor.ssl_issuer = "Test CA"
        self.monitor.ssl_last_checked_at = timezone.now()
        self.monitor.save()
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.context["ssl_status"], "ok")
        self.assertIn(response.context["monitor"].ssl_days_remaining, [29, 30])
        self.assertContains(response, "SSL Certificate")

    def test_detail_hides_ssl_for_http(self):
        http_monitor = Monitor.objects.create(owner=self.user, url="http://example.com")
        response = self.client.get(f"/monitors/{http_monitor.pk}/")
        self.assertIsNone(response.context["ssl_status"])
        self.assertNotContains(response, "SSL Certificate")

    def test_detail_shows_warning_when_expiring_soon(self):
        self.monitor.ssl_expiry_date = timezone.now() + timedelta(days=7)
        self.monitor.ssl_issuer = "Test CA"
        self.monitor.ssl_last_checked_at = timezone.now()
        self.monitor.save()
        response = self.client.get(f"/monitors/{self.monitor.pk}/")
        self.assertEqual(response.context["ssl_status"], "warning")
        self.assertContains(response, "Expiring Soon")
