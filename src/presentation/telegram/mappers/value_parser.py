from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse_int(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None


def parse_decimal(value: str) -> Decimal | None:
    raw = value.strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def telegram_profile_name(user) -> str:
    first = (getattr(user, "first_name", None) or "").strip()
    last = (getattr(user, "last_name", None) or "").strip()
    username = (getattr(user, "username", None) or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    if username:
        return username
    return "Guest"
