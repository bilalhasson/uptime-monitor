from django.contrib import admin

from .models import NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "label", "enabled")
    list_filter = ("category", "enabled")
    search_fields = ("user__username", "user__email", "category")
