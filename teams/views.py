import logging

import resend
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import InviteForm, TeamForm
from .models import Team, TeamInvite, TeamMembership
from .utils import (
    ACTIVE_TEAM_SESSION_KEY,
    get_membership,
    is_team_admin,
    user_teams,
)

logger = logging.getLogger(__name__)


def _get_member_team_or_404(user, team_id):
    """Fetch a team the user belongs to, else 404 (mirrors the owner-guard pattern)."""
    team = get_object_or_404(Team, pk=team_id)
    if not get_membership(user, team):
        raise Http404("No team matches the given query.")
    return team


def _require_admin(user, team):
    if not is_team_admin(user, team):
        return HttpResponseForbidden("Admin access required.")
    return None


@login_required
def team_list_view(request):
    memberships = (
        TeamMembership.objects.filter(user=request.user)
        .select_related("team")
        .order_by("team__name")
    )
    return render(
        request,
        "teams/team_list.html",
        {"memberships": memberships, "form": TeamForm()},
    )


@login_required
@require_POST
def team_create_view(request):
    form = TeamForm(request.POST)
    if form.is_valid():
        team = form.save(commit=False)
        team.created_by = request.user
        team.save()
        TeamMembership.objects.create(
            team=team, user=request.user, role=TeamMembership.Role.ADMIN
        )
        request.session[ACTIVE_TEAM_SESSION_KEY] = team.pk
        messages.success(request, f"Team “{team.name}” created.")
        return redirect("team-detail", team_id=team.pk)
    messages.error(request, "Please provide a team name.")
    return redirect("team-list")


@login_required
def team_detail_view(request, team_id):
    team = _get_member_team_or_404(request.user, team_id)
    memberships = team.memberships.select_related("user").all()
    pending_invites = team.invites.filter(accepted_at__isnull=True)
    return render(
        request,
        "teams/team_detail.html",
        {
            "team": team,
            "memberships": memberships,
            "pending_invites": [i for i in pending_invites if i.is_valid],
            "invite_form": InviteForm(),
            "is_admin": is_team_admin(request.user, team),
            "role_choices": TeamMembership.Role.choices,
        },
    )


@login_required
@require_POST
def team_rename_view(request, team_id):
    team = _get_member_team_or_404(request.user, team_id)
    denied = _require_admin(request.user, team)
    if denied:
        return denied
    form = TeamForm(request.POST, instance=team)
    if form.is_valid():
        form.save()
        messages.success(request, "Team renamed.")
    return redirect("team-detail", team_id=team.pk)


@login_required
@require_POST
def team_delete_view(request, team_id):
    team = _get_member_team_or_404(request.user, team_id)
    denied = _require_admin(request.user, team)
    if denied:
        return denied
    if request.session.get(ACTIVE_TEAM_SESSION_KEY) == team.pk:
        request.session.pop(ACTIVE_TEAM_SESSION_KEY, None)
    team.delete()  # its monitors revert to personal via SET_NULL
    messages.success(request, "Team deleted. Its monitors are now personal.")
    return redirect("team-list")


@login_required
@require_POST
def team_invite_view(request, team_id):
    team = _get_member_team_or_404(request.user, team_id)
    denied = _require_admin(request.user, team)
    if denied:
        return denied
    form = InviteForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid email address.")
        return redirect("team-detail", team_id=team.pk)

    invite = form.save(commit=False)
    invite.team = team
    invite.invited_by = request.user
    invite.save()

    accept_url = request.build_absolute_uri(
        f"/teams/invite/{invite.token}/"
    )
    _send_invite_email(invite, accept_url)
    messages.success(request, f"Invitation sent to {invite.email}.")
    return redirect("team-detail", team_id=team.pk)


def _send_invite_email(invite, accept_url):
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — invite email skipped for %s", invite.email)
        return
    inviter = invite.invited_by.username if invite.invited_by else "Someone"
    try:
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [invite.email],
                "subject": f"You've been invited to join {invite.team.name} on Uptime Monitor",
                "text": (
                    f"{inviter} has invited you to join the “{invite.team.name}” team "
                    f"on Uptime Monitor as a {invite.get_role_display()}.\n\n"
                    f"Accept the invitation:\n{accept_url}\n\n"
                    "This link expires in 7 days. If you don't have an account yet, "
                    "you'll be able to sign up first."
                ),
            }
        )
        logger.info("Sent team invite to %s", invite.email)
    except Exception:
        logger.exception("Failed to send team invite to %s", invite.email)


@login_required
@require_POST
def member_remove_view(request, team_id, user_id):
    team = _get_member_team_or_404(request.user, team_id)
    denied = _require_admin(request.user, team)
    if denied:
        return denied
    membership = get_object_or_404(TeamMembership, team=team, user_id=user_id)
    if membership.is_admin and team.admin_count() <= 1:
        messages.error(request, "You can't remove the last admin of a team.")
        return redirect("team-detail", team_id=team.pk)
    membership.delete()
    messages.success(request, "Member removed.")
    return redirect("team-detail", team_id=team.pk)


@login_required
@require_POST
def member_role_view(request, team_id, user_id):
    team = _get_member_team_or_404(request.user, team_id)
    denied = _require_admin(request.user, team)
    if denied:
        return denied
    membership = get_object_or_404(TeamMembership, team=team, user_id=user_id)
    new_role = request.POST.get("role")
    if new_role not in TeamMembership.Role.values:
        messages.error(request, "Invalid role.")
        return redirect("team-detail", team_id=team.pk)
    demoting_last_admin = (
        membership.is_admin
        and new_role != TeamMembership.Role.ADMIN
        and team.admin_count() <= 1
    )
    if demoting_last_admin:
        messages.error(request, "You can't demote the last admin of a team.")
        return redirect("team-detail", team_id=team.pk)
    membership.role = new_role
    membership.save(update_fields=["role"])
    messages.success(request, "Role updated.")
    return redirect("team-detail", team_id=team.pk)


@login_required
@require_POST
def team_leave_view(request, team_id):
    team = _get_member_team_or_404(request.user, team_id)
    membership = get_membership(request.user, team)
    other_members = team.memberships.exclude(pk=membership.pk).exists()
    if not other_members:
        # Sole member leaving — take the team with them (monitors revert to personal).
        if request.session.get(ACTIVE_TEAM_SESSION_KEY) == team.pk:
            request.session.pop(ACTIVE_TEAM_SESSION_KEY, None)
        team.delete()
        messages.success(request, "You left and the team was deleted (it had no other members).")
        return redirect("team-list")
    if membership.is_admin and team.admin_count() <= 1:
        messages.error(
            request,
            "You're the last admin. Promote another member to admin before leaving.",
        )
        return redirect("team-detail", team_id=team.pk)
    membership.delete()
    if request.session.get(ACTIVE_TEAM_SESSION_KEY) == team.pk:
        request.session.pop(ACTIVE_TEAM_SESSION_KEY, None)
    messages.success(request, f"You left “{team.name}”.")
    return redirect("team-list")


@login_required
@require_POST
def switch_team_view(request):
    team_id = request.POST.get("team_id")
    if not team_id:  # switch to Personal
        request.session.pop(ACTIVE_TEAM_SESSION_KEY, None)
    else:
        team = get_object_or_404(Team, pk=team_id, members=request.user)
        request.session[ACTIVE_TEAM_SESSION_KEY] = team.pk
    return redirect(request.POST.get("next") or "/")


@login_required
def invite_accept_view(request, token):
    invite = get_object_or_404(TeamInvite, token=token)
    if not invite.is_valid:
        messages.error(request, "This invitation is no longer valid.")
        return redirect("team-list")

    membership, created = TeamMembership.objects.get_or_create(
        team=invite.team,
        user=request.user,
        defaults={"role": invite.role},
    )
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_at"])
    request.session[ACTIVE_TEAM_SESSION_KEY] = invite.team.pk
    if created:
        messages.success(request, f"You've joined “{invite.team.name}”.")
    else:
        messages.info(request, f"You're already a member of “{invite.team.name}”.")
    return redirect("team-detail", team_id=invite.team.pk)
