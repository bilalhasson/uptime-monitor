from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import NotificationPreference


@login_required
def email_preferences_view(request):
    # Ensure all registered categories exist for this user
    for category, label in getattr(settings, "NOTIFICATION_CATEGORIES", []):
        NotificationPreference.objects.get_or_create(
            user=request.user,
            category=category,
            defaults={"label": label},
        )

    preferences = NotificationPreference.objects.filter(
        user=request.user
    ).order_by("category")

    if request.method == "POST":
        enabled_ids = set(request.POST.getlist("enabled"))
        for pref in preferences:
            pref.enabled = str(pref.id) in enabled_ids
            pref.save(update_fields=["enabled"])
        messages.success(request, "Email preferences updated.")
        return redirect("email-preferences")

    return render(
        request,
        "notifications/email_preferences.html",
        {"preferences": preferences},
    )
