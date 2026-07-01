from django.contrib import admin

from .models import NotificationChannel, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "label", "enabled")
    list_filter = ("category", "enabled")
    search_fields = ("user__username", "user__email", "category")


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ("user", "channel_type", "label", "enabled", "created_at")
    list_filter = ("channel_type", "enabled")
    search_fields = ("user__username", "user__email", "label")
