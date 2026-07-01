from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MonitorForm, SignupForm
from .models import CheckLog, Monitor
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
def monitor_detail_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, pk=monitor_id, owner=request.user)
    check_logs_list = list(monitor.check_logs.all()[:50])
    total_checks = len(check_logs_list)

    if total_checks > 0:
        successful = sum(1 for log in check_logs_list if log.success)
        uptime_pct = round(successful / total_checks * 100, 1)
        response_times = [log.response_time_ms for log in check_logs_list if log.response_time_ms is not None]
        avg_response_time = round(sum(response_times) / len(response_times)) if response_times else None
    else:
        uptime_pct = None
        avg_response_time = None

    return render(request, "monitors/monitor_detail.html", {
        "monitor": monitor,
        "check_logs": check_logs_list,
        "total_checks": total_checks,
        "uptime_pct": uptime_pct,
        "avg_response_time": avg_response_time,
    })


@login_required
@require_POST
def monitor_toggle_pause_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, pk=monitor_id, owner=request.user)
    monitor.is_paused = not monitor.is_paused
    monitor.save(update_fields=["is_paused"])
    action = "paused" if monitor.is_paused else "resumed"
    messages.success(request, f"Monitor {action}.")
    next_url = request.POST.get("next", "/")
    return redirect(next_url)


@login_required
def monitor_edit_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, pk=monitor_id, owner=request.user)
    if request.method == "POST":
        form = MonitorForm(request.POST, instance=monitor)
        if form.is_valid():
            form.save()
            messages.success(request, "Monitor updated.")
            return redirect("/")
    else:
        form = MonitorForm(instance=monitor)
    return render(request, "monitors/monitor_edit.html", {"form": form, "monitor": monitor})


@login_required
def monitor_delete_view(request, monitor_id):
    monitor = get_object_or_404(Monitor, pk=monitor_id, owner=request.user)
    if request.method == "POST":
        monitor.delete()
        messages.success(request, "Monitor deleted.")
        return redirect("/")
    return render(request, "monitors/monitor_confirm_delete.html", {"monitor": monitor})
