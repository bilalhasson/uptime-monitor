from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from monitors.models import Monitor

from .forms import StatusPageForm
from .models import StatusPage, StatusPageMonitor


@login_required
def statuspage_list_view(request):
    status_pages = StatusPage.objects.filter(owner=request.user)
    return render(
        request,
        "statuspages/statuspage_list.html",
        {"status_pages": status_pages},
    )


def _build_monitor_rows(user, status_page=None):
    """Build a list of dicts for the monitor selection UI."""
    monitors = Monitor.objects.filter(owner=user)
    selected_map = {}
    if status_page:
        for entry in status_page.page_monitors.all():
            selected_map[entry.monitor_id] = entry.display_name
    rows = []
    for monitor in monitors:
        rows.append(
            {
                "monitor": monitor,
                "selected": monitor.pk in selected_map,
                "display_name": selected_map.get(monitor.pk, ""),
            }
        )
    return rows


def _save_monitor_selections(request, status_page):
    """Parse POST data and save StatusPageMonitor entries."""
    status_page.page_monitors.all().delete()
    monitors = Monitor.objects.filter(owner=request.user)
    position = 0
    for monitor in monitors:
        if request.POST.get(f"monitor_{monitor.pk}"):
            display_name = request.POST.get(f"display_name_{monitor.pk}", "").strip()
            StatusPageMonitor.objects.create(
                status_page=status_page,
                monitor=monitor,
                display_name=display_name,
                position=position,
            )
            position += 1


@login_required
def statuspage_create_view(request):
    if request.method == "POST":
        form = StatusPageForm(request.POST)
        if form.is_valid():
            status_page = form.save(commit=False)
            status_page.owner = request.user
            status_page.save()
            _save_monitor_selections(request, status_page)
            messages.success(request, "Status page created.")
            return redirect("statuspage-list")
    else:
        form = StatusPageForm()
    monitor_rows = _build_monitor_rows(request.user)
    return render(
        request,
        "statuspages/statuspage_form.html",
        {"form": form, "monitor_rows": monitor_rows},
    )


@login_required
def statuspage_edit_view(request, pk):
    status_page = get_object_or_404(StatusPage, pk=pk, owner=request.user)
    if request.method == "POST":
        form = StatusPageForm(request.POST, instance=status_page)
        if form.is_valid():
            form.save()
            _save_monitor_selections(request, status_page)
            messages.success(request, "Status page updated.")
            return redirect("statuspage-list")
    else:
        form = StatusPageForm(instance=status_page)
    monitor_rows = _build_monitor_rows(request.user, status_page)
    return render(
        request,
        "statuspages/statuspage_form.html",
        {"form": form, "monitor_rows": monitor_rows, "status_page": status_page},
    )


@login_required
def statuspage_delete_view(request, pk):
    status_page = get_object_or_404(StatusPage, pk=pk, owner=request.user)
    if request.method == "POST":
        status_page.delete()
        messages.success(request, "Status page deleted.")
        return redirect("statuspage-list")
    return render(
        request,
        "statuspages/statuspage_confirm_delete.html",
        {"status_page": status_page},
    )


def statuspage_public_view(request, slug):
    status_page = get_object_or_404(StatusPage, slug=slug, is_published=True)
    entries = status_page.page_monitors.select_related("monitor").all()

    monitor_data = []
    overall_status = "pending"
    has_up = False
    has_down = False

    for entry in entries:
        monitor = entry.monitor
        check_logs_list = list(monitor.check_logs.all()[:50])
        total_checks = len(check_logs_list)

        if total_checks > 0:
            successful = sum(1 for log in check_logs_list if log.success)
            uptime_pct = round(successful / total_checks * 100, 1)
            if monitor.current_status == "up":
                has_up = True
            elif monitor.current_status == "down":
                has_down = True
        else:
            uptime_pct = None

        monitor_data.append(
            {
                "name": entry.display_name or monitor.url,
                "status": monitor.current_status,
                "uptime_pct": uptime_pct,
            }
        )

    if has_down:
        overall_status = "down"
    elif has_up:
        overall_status = "up"

    return render(
        request,
        "statuspages/statuspage_public.html",
        {
            "status_page": status_page,
            "monitor_data": monitor_data,
            "overall_status": overall_status,
        },
    )
