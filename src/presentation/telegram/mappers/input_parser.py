from __future__ import annotations

from datetime import date


def parse_period_quotes_text(text: str) -> tuple[date, date, set[str] | None]:
    parts = [x for x in text.strip().split() if x]
    if len(parts) < 2:
        raise ValueError("format")

    try:
        period_start = date.fromisoformat(parts[0])
        period_end = date.fromisoformat(parts[1])
    except ValueError as exc:
        raise ValueError("date") from exc

    if period_end < period_start:
        raise ValueError("range")

    if len(parts) == 2:
        return period_start, period_end, None

    groups_raw = " ".join(parts[2:])
    groups = {x.strip().upper() for x in groups_raw.split(",") if x.strip()}
    if not groups:
        raise ValueError("groups")
    return period_start, period_end, groups
