from django.urls import path

from . import views, views_slack

urlpatterns = [
    path("settings/notifications/", views.notification_settings_view, name="notification-settings"),
    path("settings/emails/", views.email_preferences_redirect, name="email-preferences"),
    path("settings/notifications/add-webhook/", views.add_webhook_channel_view, name="add-webhook-channel"),
    path("settings/notifications/add-sms/", views.add_sms_channel_view, name="add-sms-channel"),
    path("settings/notifications/add-push-relay/", views.add_push_relay_channel_view, name="add-push-relay-channel"),
    path("settings/notifications/channels/<int:channel_id>/toggle/", views.toggle_channel_view, name="toggle-channel"),
    path("settings/notifications/channels/<int:channel_id>/delete/", views.delete_channel_view, name="delete-channel"),
    path("settings/notifications/slack/connect/", views_slack.slack_oauth_initiate, name="slack-oauth-initiate"),
    path("settings/notifications/slack/callback/", views_slack.slack_oauth_callback, name="slack-oauth-callback"),
]
