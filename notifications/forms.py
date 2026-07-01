from django import forms

from .models import NotificationChannel


class WebhookChannelForm(forms.ModelForm):
    class Meta:
        model = NotificationChannel
        fields = ("label", "webhook_url", "webhook_secret")
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "e.g. My Webhook", "class": "form-input"}),
            "webhook_url": forms.URLInput(attrs={"placeholder": "https://example.com/webhook", "class": "form-input"}),
            "webhook_secret": forms.TextInput(attrs={"placeholder": "Optional shared secret", "class": "form-input"}),
        }


class SMSChannelForm(forms.ModelForm):
    class Meta:
        model = NotificationChannel
        fields = ("label", "sms_phone_number")
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "e.g. My Phone", "class": "form-input"}),
            "sms_phone_number": forms.TextInput(attrs={"placeholder": "+441234567890", "class": "form-input"}),
        }
        help_texts = {
            "sms_phone_number": "Phone number in E.164 format (e.g. +441234567890)",
        }
