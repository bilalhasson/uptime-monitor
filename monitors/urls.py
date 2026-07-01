from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("monitors/<int:monitor_id>/", views.monitor_detail_view, name="monitor-detail"),
    path("monitors/<int:monitor_id>/toggle-pause/", views.monitor_toggle_pause_view, name="monitor-toggle-pause"),
    path("monitors/<int:monitor_id>/delete/", views.monitor_delete_view, name="monitor-delete"),
    path("monitors/<int:monitor_id>/edit/", views.monitor_edit_view, name="monitor-edit"),
]
