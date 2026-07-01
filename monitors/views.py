from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MonitorForm, SignupForm
from .models import Monitor
from .notifications import send_monitor_added_email


def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard_view(request):
    if request.method == "POST":
        form = MonitorForm(request.POST)
        if form.is_valid():
            monitor = form.save(commit=False)
            monitor.owner = request.user
            monitor.save()
            send_monitor_added_email(monitor)
            messages.success(request, "Monitor added.")
            return redirect("/")
    else:
        form = MonitorForm()
    monitors = Monitor.objects.filter(owner=request.user)
    return render(request, "monitors/dashboard.html", {"form": form, "monitors": monitors})


@login_required
def monitor_delete_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, pk=monitor_id, owner=request.user)
    if request.method == "POST":
        monitor.delete()
        messages.success(request, "Monitor deleted.")
        return redirect("/")
    return render(request, "monitors/monitor_confirm_delete.html", {"monitor": monitor})
