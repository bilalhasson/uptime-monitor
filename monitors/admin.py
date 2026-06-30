from django.contrib import admin

from .models import Monitor


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ("url", "owner", "current_status", "last_checked_at", "created_at")
    list_filter = ("current_status",)
    search_fields = ("url", "owner__username")
