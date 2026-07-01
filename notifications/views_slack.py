import logging
import secrets

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import NotificationChannel

logger = logging.getLogger(__name__)


@login_required
def slack_oauth_initiate(request):
    state = secrets.token_urlsafe(32)
    request.session["slack_oauth_state"] = state

    client_id = settings.SLACK_CLIENT_ID
    redirect_uri = request.build_absolute_uri("/settings/notifications/slack/callback/")
    scope = "chat:write,incoming-webhook"

    authorize_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}"
        f"&scope={scope}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return redirect(authorize_url)


@login_required
def slack_oauth_callback(request):
    # User denied
    error = request.GET.get("error")
    if error:
        messages.error(request, f"Slack authorization failed: {error}")
        return redirect("notification-settings")

    # State verification
    state = request.GET.get("state", "")
    expected_state = request.session.pop("slack_oauth_state", None)
    if not state or state != expected_state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("notification-settings")

    # Exchange code for token
    code = request.GET.get("code", "")
    redirect_uri = request.build_absolute_uri("/settings/notifications/slack/callback/")

    try:
        resp = requests.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=10,
        )
        data = resp.json()
    except Exception:
        logger.exception("Slack OAuth token exchange failed")
        messages.error(request, "Failed to connect to Slack. Please try again.")
        return redirect("notification-settings")

    if not data.get("ok"):
        messages.error(request, f"Slack error: {data.get('error', 'unknown')}")
        return redirect("notification-settings")

    access_token = data.get("access_token", "")
    team_name = data.get("team", {}).get("name", "")
    webhook_info = data.get("incoming_webhook", {})
    channel_id = webhook_info.get("channel_id", "")
    channel_name = webhook_info.get("channel", "")

    NotificationChannel.objects.create(
        user=request.user,
        channel_type=NotificationChannel.ChannelType.SLACK,
        label=f"Slack: #{channel_name}" if channel_name else f"Slack: {team_name}",
        slack_access_token=access_token,
        slack_channel_id=channel_id,
        slack_channel_name=channel_name,
        slack_team_name=team_name,
    )

    messages.success(request, f"Slack connected to #{channel_name or 'channel'}.")
    return redirect("notification-settings")
