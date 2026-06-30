from django.contrib import admin

from .models import CheckLog, Monitor


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ("url", "owner", "current_status", "last_checked_at", "created_at")
    list_filter = ("current_status",)
    search_fields = ("url", "owner__username")


@admin.register(CheckLog)
class CheckLogAdmin(admin.ModelAdmin):
    list_display = ("monitor", "success", "status_code", "response_time_ms", "checked_at")
    list_filter = ("success",)
    readonly_fields = (
        "monitor",
        "status_code",
        "response_time_ms",
        "success",
        "error_message",
        "checked_at",
    )
