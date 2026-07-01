from django.urls import path

from . import views

urlpatterns = [
    path("settings/emails/", views.email_preferences_view, name="email-preferences"),
]
