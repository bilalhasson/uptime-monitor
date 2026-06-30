from django.contrib import admin
from django.urls import include, path

from monitors import views

urlpatterns = [
    path("", include("monitors.urls")),
    path("accounts/signup/", views.signup_view, name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
]
