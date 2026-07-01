from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    category = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "category")

    def __str__(self):
        return f"{self.user.username} — {self.label} ({'on' if self.enabled else 'off'})"
