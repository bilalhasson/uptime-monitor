from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Monitor


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")


class MonitorForm(forms.ModelForm):
    class Meta:
        model = Monitor
        fields = ("url", "check_interval")
        widgets = {
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                    "class": "form-input",
                }
            ),
            "check_interval": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "300",
                    "aria-describedby": "help_id_check_interval",
                }
            ),
        }
