from django.conf import settings
from django.db import models


class StatusPage(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="status_pages",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class StatusPageMonitor(models.Model):
    status_page = models.ForeignKey(
        StatusPage,
        on_delete=models.CASCADE,
        related_name="page_monitors",
    )
    monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.CASCADE,
        related_name="status_page_entries",
    )
    display_name = models.CharField(max_length=200, blank=True, default="")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        unique_together = ("status_page", "monitor")

    def __str__(self):
        return f"{self.status_page.title} — {self.display_name or self.monitor.url}"
