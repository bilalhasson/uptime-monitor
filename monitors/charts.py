"""Uptime-history chart data for the monitor detail page.

Everything is aggregated in the database (bucketed by hour or day) and the SVG
geometry is computed here in Python, so the template only iterates ready-made
primitives. No JS, no charting library — the views emit inline SVG.
"""
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from .models import CheckLog

# --- range configuration ---------------------------------------------------
# key -> (label, number of buckets, granularity)
RANGES = {
    "24h": {"label": "24 hours", "buckets": 24, "unit": "hour"},
    "7d": {"label": "7 days", "buckets": 7, "unit": "day"},
    "30d": {"label": "30 days", "buckets": 30, "unit": "day"},
}
DEFAULT_RANGE = "7d"

# --- status palette (matches the app's existing badges) ---------------------
COLOR_UP = "#16a34a"       # green-600  — 100% success
COLOR_PARTIAL = "#d97706"  # amber-600  — degraded (partial failures)
COLOR_DOWN = "#dc2626"     # red-600    — 0% success
COLOR_NODATA = "#e5e7eb"   # gray-200   — no checks in this bucket
LINE_COLOR = "#2563eb"     # primary blue — response-time series

# --- SVG geometry -----------------------------------------------------------
STRIP_W = 720
STRIP_H = 44
BAR_GAP = 2
BAR_RADIUS = 2

LINE_W = 720
LINE_H = 160
LINE_PAD = 6


def resolve_range(range_key):
    return range_key if range_key in RANGES else DEFAULT_RANGE


def _bucket_keys(unit, count):
    """Generate the full ordered list of bucket keys ending at the current period.

    Returning every period (not just those with data) keeps the strip a fixed
    width and renders gaps as explicit "no data" bars.
    """
    now = timezone.now()
    if unit == "hour":
        end = now.replace(minute=0, second=0, microsecond=0)
        keys = [end - timedelta(hours=i) for i in range(count - 1, -1, -1)]
        cutoff = keys[0]
    else:  # day
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        keys = [today - timedelta(days=i) for i in range(count - 1, -1, -1)]
        cutoff = keys[0]
    return keys, cutoff


def _aggregate(monitor, unit, cutoff):
    trunc = TruncHour if unit == "hour" else TruncDate
    rows = (
        CheckLog.objects.filter(monitor=monitor, checked_at__gte=cutoff)
        .annotate(bucket=trunc("checked_at"))
        .values("bucket")
        .annotate(
            total=Count("id"),
            successes=Count("id", filter=Q(success=True)),
            avg_rt=Avg("response_time_ms"),
        )
    )
    # TruncDate yields a date; normalise both key types to a comparable value.
    return {row["bucket"]: row for row in rows}


def _bucket_label(key, unit):
    if unit == "hour":
        return key.strftime("%b %-d %H:%M")
    return key.strftime("%b %-d")


def _bar_color(uptime_pct):
    if uptime_pct is None:
        return COLOR_NODATA
    if uptime_pct >= 100:
        return COLOR_UP
    if uptime_pct <= 0:
        return COLOR_DOWN
    return COLOR_PARTIAL


def build_uptime_strip(monitor, range_key):
    """Return the uptime bar-strip primitives for the given range."""
    cfg = RANGES[range_key]
    unit, count = cfg["unit"], cfg["buckets"]
    keys, cutoff = _bucket_keys(unit, count)
    agg = _aggregate(monitor, unit, cutoff)
    if unit == "day":
        agg = {(k.date() if hasattr(k, "date") else k): v for k, v in agg.items()}

    bar_w = STRIP_W / count
    bars = []
    checked_total = 0
    success_total = 0
    for i, key in enumerate(keys):
        lookup = key.date() if unit == "day" else key
        row = agg.get(lookup)
        if row and row["total"]:
            total = row["total"]
            uptime = round(row["successes"] / total * 100, 1)
            checked_total += total
            success_total += row["successes"]
            title = f"{_bucket_label(key, unit)} · {uptime}% up · {total} checks"
        else:
            uptime = None
            title = f"{_bucket_label(key, unit)} · no data"
        bars.append(
            {
                "x": round(i * bar_w, 2),
                "width": round(bar_w - BAR_GAP, 2),
                "color": _bar_color(uptime),
                "title": title,
            }
        )

    overall = round(success_total / checked_total * 100, 1) if checked_total else None
    return {
        "bars": bars,
        "view_w": STRIP_W,
        "view_h": STRIP_H,
        "radius": BAR_RADIUS,
        "overall_uptime": overall,
        "has_data": checked_total > 0,
    }


def _nice_ceiling(value):
    """Round a max response time up to a readable axis top."""
    if value <= 0:
        return 1
    for step in (50, 100, 250, 500, 1000, 2500, 5000, 10000):
        if value <= step:
            return step
    # Round up to the next 5000 beyond the table.
    return int((value // 5000 + 1) * 5000)


def build_response_series(monitor, range_key):
    """Return the response-time line primitives (avg ms per bucket)."""
    cfg = RANGES[range_key]
    unit, count = cfg["unit"], cfg["buckets"]
    keys, cutoff = _bucket_keys(unit, count)
    agg = _aggregate(monitor, unit, cutoff)
    if unit == "day":
        agg = {(k.date() if hasattr(k, "date") else k): v for k, v in agg.items()}

    values = []  # (index, avg_rt, label)
    for i, key in enumerate(keys):
        lookup = key.date() if unit == "day" else key
        row = agg.get(lookup)
        avg = row["avg_rt"] if row and row.get("avg_rt") is not None else None
        if avg is not None:
            values.append((i, round(avg), _bucket_label(key, unit)))

    if not values:
        return {"has_data": False, "view_w": LINE_W, "view_h": LINE_H}

    y_max = _nice_ceiling(max(v[1] for v in values))
    span = max(count - 1, 1)
    plot_h = LINE_H - 2 * LINE_PAD

    def px(i):
        return round(i / span * LINE_W, 2)

    def py(v):
        return round(LINE_H - LINE_PAD - (v / y_max) * plot_h, 2)

    points = " ".join(f"{px(i)},{py(v)}" for i, v, _ in values)
    markers = [
        {"cx": px(i), "cy": py(v), "title": f"{label} · {v} ms"}
        for i, v, label in values
    ]
    gridlines = [
        {"y": py(0), "label": "0"},
        {"y": py(y_max / 2), "label": str(int(y_max / 2))},
        {"y": py(y_max), "label": str(y_max)},
    ]
    return {
        "has_data": True,
        "points": points,
        "markers": markers,
        "gridlines": gridlines,
        "line_color": LINE_COLOR,
        "view_w": LINE_W,
        "view_h": LINE_H,
        "y_max": y_max,
    }


def range_options(active_key):
    """Ordered list for the range toggle UI."""
    return [
        {"key": k, "label": RANGES[k]["label"], "active": k == active_key}
        for k in RANGES
    ]
