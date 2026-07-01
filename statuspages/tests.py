from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from monitors.models import CheckLog, Monitor

from .forms import StatusPageForm
from .models import StatusPage, StatusPageMonitor


class StatusPageModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.page = StatusPage.objects.create(
            owner=self.user, title="Acme Status", slug="acme"
        )
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_str_returns_title(self):
        self.assertEqual(str(self.page), "Acme Status")

    def test_slug_unique(self):
        with self.assertRaises(IntegrityError):
            StatusPage.objects.create(
                owner=self.user, title="Duplicate", slug="acme"
            )

    def test_cascade_deletes_page_monitors(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        self.assertEqual(StatusPageMonitor.objects.count(), 1)
        self.page.delete()
        self.assertEqual(StatusPageMonitor.objects.count(), 0)

    def test_monitor_deletion_cascades_to_entries(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        self.assertEqual(StatusPageMonitor.objects.count(), 1)
        self.monitor.delete()
        self.assertEqual(StatusPageMonitor.objects.count(), 0)

    def test_unique_together_on_through_model(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        with self.assertRaises(IntegrityError):
            StatusPageMonitor.objects.create(
                status_page=self.page, monitor=self.monitor, position=1
            )


class StatusPageFormTests(TestCase):
    def test_valid_data(self):
        form = StatusPageForm(
            data={"title": "My Page", "slug": "my-page", "is_published": True}
        )
        self.assertTrue(form.is_valid())

    def test_title_required(self):
        form = StatusPageForm(data={"title": "", "slug": "my-page", "is_published": True})
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_slug_required(self):
        form = StatusPageForm(data={"title": "My Page", "slug": "", "is_published": True})
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)


class StatusPageCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")

    def test_login_required(self):
        response = self.client.get(reverse("statuspage-create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_renders_form(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("statuspage-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Status Page")

    def test_post_creates_and_redirects(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(
            reverse("statuspage-create"),
            {"title": "Test Page", "slug": "test-page", "is_published": True},
        )
        self.assertRedirects(response, reverse("statuspage-list"))
        self.assertEqual(StatusPage.objects.count(), 1)
        page = StatusPage.objects.first()
        self.assertEqual(page.owner, self.user)
        self.assertEqual(page.title, "Test Page")

    def test_post_with_monitors_creates_entries(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(
            reverse("statuspage-create"),
            {
                "title": "Test Page",
                "slug": "test-page",
                "is_published": True,
                f"monitor_{self.monitor.pk}": "1",
                f"display_name_{self.monitor.pk}": "API Server",
            },
        )
        self.assertRedirects(response, reverse("statuspage-list"))
        self.assertEqual(StatusPageMonitor.objects.count(), 1)
        entry = StatusPageMonitor.objects.first()
        self.assertEqual(entry.display_name, "API Server")
        self.assertEqual(entry.monitor, self.monitor)


class StatusPageEditViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.other_user = User.objects.create_user(username="bob", password="testpass123")
        self.monitor = Monitor.objects.create(owner=self.user, url="https://example.com")
        self.page = StatusPage.objects.create(
            owner=self.user, title="Original", slug="original"
        )

    def test_login_required(self):
        response = self.client.get(reverse("statuspage-edit", args=[self.page.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_prefills_form(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("statuspage-edit", args=[self.page.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original")

    def test_non_owner_gets_404(self):
        self.client.login(username="bob", password="testpass123")
        response = self.client.get(reverse("statuspage-edit", args=[self.page.pk]))
        self.assertEqual(response.status_code, 404)

    def test_post_updates_page(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(
            reverse("statuspage-edit", args=[self.page.pk]),
            {"title": "Updated", "slug": "updated", "is_published": True},
        )
        self.assertRedirects(response, reverse("statuspage-list"))
        self.page.refresh_from_db()
        self.assertEqual(self.page.title, "Updated")

    def test_post_updates_monitor_selections(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        monitor2 = Monitor.objects.create(owner=self.user, url="https://other.com")
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(
            reverse("statuspage-edit", args=[self.page.pk]),
            {
                "title": "Updated",
                "slug": "original",
                "is_published": True,
                f"monitor_{monitor2.pk}": "1",
                f"display_name_{monitor2.pk}": "Other",
            },
        )
        self.assertRedirects(response, reverse("statuspage-list"))
        entries = StatusPageMonitor.objects.filter(status_page=self.page)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().monitor, monitor2)
        self.assertEqual(entries.first().display_name, "Other")


class StatusPageDeleteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.other_user = User.objects.create_user(username="bob", password="testpass123")
        self.page = StatusPage.objects.create(
            owner=self.user, title="To Delete", slug="to-delete"
        )

    def test_login_required(self):
        response = self.client.get(reverse("statuspage-delete", args=[self.page.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_shows_confirmation(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.get(reverse("statuspage-delete", args=[self.page.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "To Delete")

    def test_non_owner_gets_404(self):
        self.client.login(username="bob", password="testpass123")
        response = self.client.get(reverse("statuspage-delete", args=[self.page.pk]))
        self.assertEqual(response.status_code, 404)

    def test_post_deletes_page(self):
        self.client.login(username="alice", password="testpass123")
        response = self.client.post(reverse("statuspage-delete", args=[self.page.pk]))
        self.assertRedirects(response, reverse("statuspage-list"))
        self.assertEqual(StatusPage.objects.count(), 0)


class StatusPagePublicViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass123")
        self.page = StatusPage.objects.create(
            owner=self.user, title="Public Page", slug="public", is_published=True
        )
        self.monitor = Monitor.objects.create(
            owner=self.user, url="https://example.com", current_status="up"
        )

    def test_published_page_accessible_without_login(self):
        response = self.client.get(reverse("statuspage-public", args=["public"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public Page")

    def test_unpublished_returns_404(self):
        self.page.is_published = False
        self.page.save()
        response = self.client.get(reverse("statuspage-public", args=["public"]))
        self.assertEqual(response.status_code, 404)

    def test_shows_monitor_data(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        response = self.client.get(reverse("statuspage-public", args=["public"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100.0% uptime")

    def test_overall_status_up(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        CheckLog.objects.create(monitor=self.monitor, success=True, status_code=200)
        response = self.client.get(reverse("statuspage-public", args=["public"]))
        self.assertContains(response, "All Systems Operational")

    def test_display_name_used_when_set(self):
        StatusPageMonitor.objects.create(
            status_page=self.page,
            monitor=self.monitor,
            display_name="API Server",
            position=0,
        )
        response = self.client.get(reverse("statuspage-public", args=["public"]))
        self.assertContains(response, "API Server")

    def test_falls_back_to_url_when_no_display_name(self):
        StatusPageMonitor.objects.create(
            status_page=self.page, monitor=self.monitor, position=0
        )
        response = self.client.get(reverse("statuspage-public", args=["public"]))
        self.assertContains(response, "https://example.com")
