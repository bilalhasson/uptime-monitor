from django.conf import settings
from django.db import models


class Monitor(models.Model):
    class Status(models.TextChoices):
        UP = "up", "Up"
        DOWN = "down", "Down"
        PENDING = "pending", "Pending"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monitors",
    )
    url = models.URLField(max_length=2048)
    check_interval = models.PositiveIntegerField(
        default=300, help_text="Check interval in seconds"
    )
    current_status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url


class CheckLog(models.Model):
    monitor = models.ForeignKey(
        Monitor, on_delete=models.CASCADE, related_name="check_logs"
    )
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField()
    error_message = models.CharField(max_length=255, blank=True, default="")
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(
                fields=["monitor", "-checked_at"],
                name="checklog_monitor_checked",
            ),
        ]

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"{self.monitor} — {status} @ {self.checked_at}"
