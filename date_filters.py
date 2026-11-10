"""Date-range helpers for the profile page filter (parsing, labels, presets)."""
from datetime import date, datetime, timedelta

from flask import url_for

DATE_FORMAT = "%Y-%m-%d"
DISPLAY_FORMAT = "%d %b %Y"

INVALID_DATE_ERROR = "Enter dates as YYYY-MM-DD."
REVERSED_RANGE_ERROR = "The start date must be on or before the end date."


def parse_iso_date(value):
    """Return a normalised 'YYYY-MM-DD' string, or None if invalid.

    strptime accepts non-padded input such as '2026-1-5'; re-formatting keeps
    the value comparable as text against the stored ISO dates.
    """
    try:
        return datetime.strptime(value, DATE_FORMAT).strftime(DATE_FORMAT)
    except ValueError:
        return None


def parse_date_range(args):
    """Return (start, end, error) from request args.

    Blank values mean "absent" and raise no error. An invalid value is
    dropped with an error while the other, valid value still applies. A
    reversed range drops both values.
    """
    raw_start = args.get("start", "").strip()
    raw_end = args.get("end", "").strip()
    start = parse_iso_date(raw_start) if raw_start else None
    end = parse_iso_date(raw_end) if raw_end else None

    error = None
    if (raw_start and start is None) or (raw_end and end is None):
        error = INVALID_DATE_ERROR
    if start and end and start > end:
        start = end = None
        error = REVERSED_RANGE_ERROR
    return start, end, error


def format_range_label(start, end):
    """Human-readable description of the active range, or None."""
    def fmt(iso):
        return date.fromisoformat(iso).strftime(DISPLAY_FORMAT)

    if start and end:
        return f"Showing {fmt(start)} – {fmt(end)}"
    if start:
        return f"From {fmt(start)}"
    if end:
        return f"Up to {fmt(end)}"
    return None


def build_presets(start, end, today=None):
    """Quick-range links; `active` marks the one matching the current range."""
    today = today or date.today()
    specs = [
        ("This month", today.replace(day=1).isoformat(), today.isoformat()),
        ("Last 30 days", (today - timedelta(days=29)).isoformat(), today.isoformat()),
        ("All time", None, None),
    ]
    # url_for drops None values, so "All time" links to plain /profile.
    return [
        {
            "label": label,
            "url": url_for("profile", start=p_start, end=p_end),
            "active": (p_start, p_end) == (start, end),
        }
        for label, p_start, p_end in specs
    ]
