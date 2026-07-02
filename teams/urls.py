from django.urls import path

from . import views

urlpatterns = [
    path("settings/teams/", views.team_list_view, name="team-list"),
    path("settings/teams/create/", views.team_create_view, name="team-create"),
    path("settings/teams/switch/", views.switch_team_view, name="switch-team"),
    path("settings/teams/<int:team_id>/", views.team_detail_view, name="team-detail"),
    path("settings/teams/<int:team_id>/rename/", views.team_rename_view, name="team-rename"),
    path("settings/teams/<int:team_id>/delete/", views.team_delete_view, name="team-delete"),
    path("settings/teams/<int:team_id>/invite/", views.team_invite_view, name="team-invite"),
    path("settings/teams/<int:team_id>/leave/", views.team_leave_view, name="team-leave"),
    path(
        "settings/teams/<int:team_id>/members/<int:user_id>/remove/",
        views.member_remove_view,
        name="member-remove",
    ),
    path(
        "settings/teams/<int:team_id>/members/<int:user_id>/role/",
        views.member_role_view,
        name="member-role",
    ),
    path("teams/invite/<str:token>/", views.invite_accept_view, name="invite-accept"),
]
