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
        fields = ("url",)
        widgets = {
            "url": forms.URLInput(
                attrs={
                    "placeholder": "https://example.com",
                    "style": "padding:0.5rem; width:100%; max-width:400px; border:1px solid #ccc; border-radius:4px; font-size:0.875rem;",
                }
            ),
        }
