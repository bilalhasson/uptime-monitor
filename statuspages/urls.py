from django.urls import path

from . import views

urlpatterns = [
    path(
        "status/<slug:slug>/",
        views.statuspage_public_view,
        name="statuspage-public",
    ),
    path(
        "status-pages/",
        views.statuspage_list_view,
        name="statuspage-list",
    ),
    path(
        "status-pages/create/",
        views.statuspage_create_view,
        name="statuspage-create",
    ),
    path(
        "status-pages/<int:pk>/edit/",
        views.statuspage_edit_view,
        name="statuspage-edit",
    ),
    path(
        "status-pages/<int:pk>/delete/",
        views.statuspage_delete_view,
        name="statuspage-delete",
    ),
]
