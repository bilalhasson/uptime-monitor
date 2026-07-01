from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SMSChannelForm, WebhookChannelForm
from .models import NotificationChannel, NotificationPreference


@login_required
def notification_settings_view(request):
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
        messages.success(request, "Notification preferences updated.")
        return redirect("notification-settings")

    channels = NotificationChannel.objects.filter(user=request.user)
    slack_client_id = getattr(settings, "SLACK_CLIENT_ID", "")
    twilio_configured = bool(getattr(settings, "TWILIO_ACCOUNT_SID", ""))

    return render(
        request,
        "notifications/notification_settings.html",
        {
            "preferences": preferences,
            "channels": channels,
            "slack_client_id": slack_client_id,
            "twilio_configured": twilio_configured,
        },
    )


@login_required
def add_webhook_channel_view(request):
    if request.method == "POST":
        form = WebhookChannelForm(request.POST)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.user = request.user
            channel.channel_type = NotificationChannel.ChannelType.WEBHOOK
            channel.save()
            messages.success(request, "Webhook channel added.")
            return redirect("notification-settings")
    else:
        form = WebhookChannelForm()

    return render(request, "notifications/add_webhook.html", {"form": form})


@login_required
def add_sms_channel_view(request):
    if request.method == "POST":
        form = SMSChannelForm(request.POST)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.user = request.user
            channel.channel_type = NotificationChannel.ChannelType.SMS
            channel.save()
            messages.success(request, "SMS channel added.")
            return redirect("notification-settings")
    else:
        form = SMSChannelForm()

    return render(request, "notifications/add_sms.html", {"form": form})


@login_required
def toggle_channel_view(request, channel_id):
    channel = get_object_or_404(NotificationChannel, pk=channel_id, user=request.user)
    if request.method == "POST":
        channel.enabled = not channel.enabled
        channel.save(update_fields=["enabled"])
        state = "enabled" if channel.enabled else "disabled"
        messages.success(request, f"Channel {state}.")
    return redirect("notification-settings")


@login_required
def delete_channel_view(request, channel_id):
    channel = get_object_or_404(NotificationChannel, pk=channel_id, user=request.user)
    if request.method == "POST":
        channel.delete()
        messages.success(request, "Channel deleted.")
    return redirect("notification-settings")


def email_preferences_redirect(request):
    return redirect("notification-settings")
