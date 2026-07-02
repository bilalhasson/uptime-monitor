"""Team membership helpers. Kept free of any monitors import (one-way dependency)."""
from .models import Team, TeamMembership

ACTIVE_TEAM_SESSION_KEY = "active_team_id"


def user_teams(user):
    return Team.objects.filter(members=user)


def get_membership(user, team):
    return TeamMembership.objects.filter(team=team, user=user).first()


def is_member(user, team):
    return TeamMembership.objects.filter(team=team, user=user).exists()


def is_team_admin(user, team):
    return TeamMembership.objects.filter(
        team=team, user=user, role=TeamMembership.Role.ADMIN
    ).exists()


def get_active_team(request):
    """Resolve the active team from the session.

    Returns None (the "Personal" context) when unset or when the user is no
    longer a member of the stored team.
    """
    team_id = request.session.get(ACTIVE_TEAM_SESSION_KEY)
    if not team_id:
        return None
    team = Team.objects.filter(pk=team_id, members=request.user).first()
    if team is None:
        # Stale reference — clear it so we don't keep looking it up.
        request.session.pop(ACTIVE_TEAM_SESSION_KEY, None)
    return team
