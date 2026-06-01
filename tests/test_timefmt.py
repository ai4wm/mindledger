from __future__ import annotations

from datetime import datetime, timezone

from memsearch.timefmt import format_for_display, utc_now_iso


def test_utc_now_iso_uses_z_suffix() -> None:
    value = utc_now_iso()
    assert value.endswith("Z")


def test_format_for_display_uses_kst() -> None:
    dt = datetime(2026, 6, 1, 2, 51, tzinfo=timezone.utc)
    assert format_for_display(dt) == "2026-06-01 11:51 KST"
