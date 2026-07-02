import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

INVITE_TTL = timedelta(days=7)


def _default_invite_expiry():
    return timezone.now() + INVITE_TTL


def generate_invite_token():
    return secrets.token_urlsafe(32)


class Team(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_teams",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="TeamMembership",
        related_name="teams",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def admin_count(self):
        return self.memberships.filter(role=TeamMembership.Role.ADMIN).count()


class TeamMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "user")
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} — {self.team} ({self.role})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN


class TeamInvite(models.Model):
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="invites"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=10,
        choices=TeamMembership.Role.choices,
        default=TeamMembership.Role.MEMBER,
    )
    token = models.CharField(
        max_length=64, unique=True, db_index=True, default=generate_invite_token
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_invite_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.email} → {self.team}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return self.accepted_at is None and not self.is_expired
