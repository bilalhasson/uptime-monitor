"""Access control for monitors under the hybrid owner/team model.

A monitor is visible to a user when they own it OR they are a member of the
team it belongs to. This is the single source of truth for that rule.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Monitor


def visible_monitors(user):
    """Monitors the user may view/manage: personal (owned) or via team membership."""
    return Monitor.objects.filter(
        Q(owner=user) | Q(team__members=user)
    ).distinct()


def get_monitor_or_404(user, monitor_id):
    return get_object_or_404(visible_monitors(user), pk=monitor_id)
