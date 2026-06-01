"""Time formatting helpers for memsearch and plugin layers."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_DISPLAY_TIMEZONE = "Asia/Seoul"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time in RFC 3339-style ISO format."""
    return utc_now().isoformat().replace("+00:00", "Z")


def format_for_display(dt: datetime | None = None, *, timezone_name: str = DEFAULT_DISPLAY_TIMEZONE) -> str:
    """Format *dt* in a human-facing local time string.

    Defaults to Asia/Seoul because the project primarily records memory
    for a Korean-speaking operator, while preserving UTC for storage.
    """
    instant = dt or utc_now()
    local_dt = instant.astimezone(ZoneInfo(timezone_name))
    tz_abbrev = local_dt.tzname() or timezone_name
    return local_dt.strftime(f"%Y-%m-%d %H:%M {tz_abbrev}")
