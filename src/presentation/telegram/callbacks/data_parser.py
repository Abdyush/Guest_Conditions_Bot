from __future__ import annotations


NAV_MAIN = "nav:main"
NAV_BACK_MAIN = "nav:back_main"
NAV_BACK_QUOTES_GROUP = "nav:back_quotes_group"
NAV_BACK_QUOTES_CALENDAR = "nav:back_quotes_calendar"
NAV_BACK_QUOTES_CATEGORIES = "nav:back_quotes_categories"
NAV_BACK_BEST_GROUPS = "nav:back_best_groups"
NAV_BACK_AVAILABLE_CATEGORIES = "nav:back_avail_categories"
NAV_BACK_NOTIFIED_CATEGORIES = "nav:back_notif_categories"

PREFIX_BEST_GROUP = "bestgrp:"
PREFIX_QUOTES_GROUP = "qgrp:"
PREFIX_CALENDAR = "cal:"
PREFIX_QUOTES_CATEGORY = "qcat:"
PREFIX_AVAILABLE_CATEGORY = "availcat:"
PREFIX_AVAILABLE_PERIOD = "availprd:"
PREFIX_REGISTRATION_CATEGORY = "regcat:"
PREFIX_NOTIFIED_CATEGORY = "ncat:"
PREFIX_NOTIFIED_PERIOD = "nprd:"
PREFIX_NOTIFIED_OFFER = "noff:"


def parse_suffix(data: str, prefix: str) -> str | None:
    if not data.startswith(prefix):
        return None
    return data.split(":", 1)[1]


def parse_single_index(data: str, prefix: str) -> int | None:
    raw = parse_suffix(data, prefix)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_two_indices(data: str, prefix: str) -> tuple[int, int] | None:
    if not data.startswith(prefix):
        return None
    parts = data.split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None
