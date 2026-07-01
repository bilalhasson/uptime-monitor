from django import forms

from .models import StatusPage


class StatusPageForm(forms.ModelForm):
    class Meta:
        model = StatusPage
        fields = ("title", "slug", "is_published")
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "My Status Page",
                    "class": "form-input",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "placeholder": "my-company",
                    "class": "form-input",
                }
            ),
        }
