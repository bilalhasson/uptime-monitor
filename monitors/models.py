from django.conf import settings
from django.db import models
from django.utils import timezone


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
    is_paused = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # SSL certificate fields
    ssl_expiry_date = models.DateTimeField(null=True, blank=True)
    ssl_issuer = models.CharField(max_length=255, blank=True, default="")
    ssl_last_checked_at = models.DateTimeField(null=True, blank=True)
    ssl_error = models.CharField(max_length=255, blank=True, default="")
    ssl_expiry_notified = models.BooleanField(default=False)

    @property
    def ssl_days_remaining(self):
        if self.ssl_expiry_date:
            return (self.ssl_expiry_date - timezone.now()).days
        return None

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
