from django import forms

from .models import Team, TeamInvite, TeamMembership


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "e.g. Platform Team", "class": "form-input"}
            ),
        }


class InviteForm(forms.ModelForm):
    class Meta:
        model = TeamInvite
        fields = ("email", "role")
        widgets = {
            "email": forms.EmailInput(
                attrs={"placeholder": "teammate@example.com", "class": "form-input"}
            ),
            "role": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = TeamMembership.Role.choices
