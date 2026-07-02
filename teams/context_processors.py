from .utils import get_active_team, user_teams


def team_context(request):
    """Expose the active team and the user's teams to every template (nav switcher)."""
    if not request.user.is_authenticated:
        return {}
    return {
        "active_team": get_active_team(request),
        "user_teams": user_teams(request.user),
    }
