from django.contrib import admin

from .models import StatusPage, StatusPageMonitor


class StatusPageMonitorInline(admin.TabularInline):
    model = StatusPageMonitor
    extra = 1


@admin.register(StatusPage)
class StatusPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "owner", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "slug", "owner__username")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [StatusPageMonitorInline]
