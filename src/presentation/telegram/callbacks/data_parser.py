from __future__ import annotations


NAV_MAIN = "nav:main"
NAV_BACK_MAIN = "nav:back_main"
NAV_BACK_QUOTES_GROUP = "nav:back_quotes_group"
NAV_BACK_QUOTES_CALENDAR = "nav:back_quotes_calendar"
NAV_BACK_QUOTES_CATEGORIES = "nav:back_quotes_categories"
NAV_BACK_BEST_GROUPS = "nav:back_best_groups"
NAV_BACK_BEST_CATEGORIES = "nav:back_best_categories"
NAV_BACK_AVAILABLE_CATEGORIES = "nav:back_avail_categories"
NAV_BACK_NOTIFIED_CATEGORIES = "nav:back_notif_categories"
NAV_BACK_NOTIFICATION_GROUPS = "nav:back_notification_groups"

PREFIX_BEST_GROUP = "bestgrp:"
PREFIX_BEST_CATEGORY = "bestcat:"
PREFIX_BEST_OFFER = "bestoff:"
PREFIX_BEST_RESULT = "bestres:"
PREFIX_NOTIFICATION_GROUP = "ntfgrp:"
PREFIX_NOTIFICATION_CATEGORY = "ntfcat:"
PREFIX_NOTIFICATION_PERIOD = "ntfprd:"
PREFIX_NOTIFICATION_OFFER = "ntfoff:"
PREFIX_QUOTES_GROUP = "qgrp:"
PREFIX_CALENDAR = "cal:"
PREFIX_QUOTES_CATEGORY = "qcat:"
PREFIX_QUOTES_OFFER = "qoff:"
PREFIX_QUOTES_RESULT = "qres:"
PREFIX_AVAILABLE_CATEGORY = "availcat:"
PREFIX_AVAILABLE_PERIOD = "availprd:"
PREFIX_AVAILABLE_OFFER = "avoff:"
PREFIX_AVAILABLE_REQUEST = "avreq:"
PREFIX_AVAILABLE_REQUEST_CALENDAR = "avreq:cal:"
PREFIX_REGISTRATION_CATEGORY = "regcat:"
PREFIX_EDIT_FIELD = "editfld:"
PREFIX_EDIT_LOYALTY = "editloy:"
PREFIX_EDIT_BANK = "editbank:"
PREFIX_EDIT_NAV = "editnav:"
PREFIX_ADMIN = "admin:"
ADMIN_OPEN_SYSTEM = "admin:open:system"
ADMIN_OPEN_REPORTS = "admin:open:reports"
ADMIN_OPEN_STATISTICS = "admin:open:statistics"
ADMIN_SYSTEM_RATES = "admin:sys:rates"
ADMIN_SYSTEM_OFFERS = "admin:sys:offers"
ADMIN_SYSTEM_RECALC = "admin:sys:recalc"
ADMIN_REPORT_PARSER_RATES = "admin:rep:parser_rates"
ADMIN_REPORT_PARSER_OFFERS = "admin:rep:parser_offers"
ADMIN_REPORT_RECALCULATION = "admin:rep:recalculation"
ADMIN_REPORT_USER_ERRORS = "admin:rep:user_errors"
ADMIN_STAT_TOTAL_USERS = "admin:stat:total_users"
ADMIN_STAT_PRICE_TABLE = "admin:stat:price_table"
ADMIN_STAT_NEW_USERS = "admin:stat:new_users"
ADMIN_STAT_BLOCKED = "admin:stat:blocked"
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
