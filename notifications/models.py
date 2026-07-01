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


class NotificationChannel(models.Model):
    class ChannelType(models.TextChoices):
        SLACK = "slack", "Slack"
        WEBHOOK = "webhook", "Webhook"
        SMS = "sms", "SMS"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_channels",
    )
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices)
    label = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)

    # Slack
    slack_access_token = models.CharField(max_length=512, blank=True, default="")
    slack_channel_id = models.CharField(max_length=100, blank=True, default="")
    slack_channel_name = models.CharField(max_length=200, blank=True, default="")
    slack_team_name = models.CharField(max_length=200, blank=True, default="")

    # Webhook
    webhook_url = models.URLField(max_length=2048, blank=True, default="")
    webhook_secret = models.CharField(max_length=255, blank=True, default="")

    # SMS
    sms_phone_number = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.get_channel_type_display()}: {self.label}"
