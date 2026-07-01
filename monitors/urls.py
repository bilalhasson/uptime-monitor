from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("monitors/<int:monitor_id>/delete/", views.monitor_delete_view, name="monitor-delete"),
    path("monitors/<int:monitor_id>/edit/", views.monitor_edit_view, name="monitor-edit"),
]
