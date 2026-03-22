from __future__ import annotations

from datetime import date, timedelta


def format_ui_date(value: date) -> str:
    return value.strftime("%d.%m.%y")


def booking_checkout_date(end_date_inclusive: date) -> date:
    return end_date_inclusive + timedelta(days=1)


def booking_coverage_end(end_date_exclusive: date) -> date:
    return end_date_exclusive - timedelta(days=1)


def format_booking_period(*, start_date: date, end_date_inclusive: date, separator: str = " \u2013 ") -> str:
    return f"{format_ui_date(start_date)}{separator}{format_ui_date(booking_checkout_date(end_date_inclusive))}"


def format_selected_booking_period(*, checkin: date, checkout: date, separator: str = " \u2013 ") -> str:
    return f"{format_ui_date(checkin)}{separator}{format_ui_date(checkout)}"
