from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.presentation.telegram.presenters.booking_period import (
    format_booking_period,
    format_selected_booking_period,
    format_ui_date,
)


def render_interest_request_calendar_prompt(*, category_name: str) -> str:
    return f"{category_name}\n\n\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0436\u0435\u043b\u0430\u0435\u043c\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434 \u043f\u0440\u043e\u0436\u0438\u0432\u0430\u043d\u0438\u044f."


def render_interest_request_tariff_prompt(*, category_name: str, checkin: date, checkout: date) -> str:
    return (
        f"{category_name}\n"
        f"\u041f\u0435\u0440\u0438\u043e\u0434 {format_selected_booking_period(checkin=checkin, checkout=checkout)}\n\n"
        "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0442\u0430\u0440\u0438\u0444."
    )


def render_interest_request_message(
    *,
    category_name: str,
    period_start: date,
    period_end: date,
    tariff_name: str,
    open_price_minor: int | None,
    preliminary_price_minor: int | None,
    adults: int,
    children_4_13: int,
    infants_0_3: int,
    loyalty_status: str | None,
    special_offers: list[tuple[date, date, str]],
) -> str:
    guest_lines = [f"\u0412\u0437\u0440\u043e\u0441\u043b\u044b\u0435: {adults}"]
    if children_4_13 > 0:
        guest_lines.append(f"\u0414\u0435\u0442\u0438 (4\u201313 \u043b\u0435\u0442): {children_4_13}")
    if infants_0_3 > 0:
        guest_lines.append(f"\u0414\u0435\u0442\u0438 (0\u20133 \u043b\u0435\u0442): {infants_0_3}")

    discount_lines: list[str] = []
    if loyalty_status:
        discount_lines.append(f"\u0441\u0442\u0430\u0442\u0443\u0441 \u0432 \u043f\u043b: {loyalty_status.lower()}")
    for offer_start, offer_end, offer_title in special_offers:
        discount_lines.append(
            f'\u0441\u043f\u0435\u0446\u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435: {format_booking_period(start_date=offer_start, end_date_inclusive=offer_end)} "{offer_title}"'
        )

    open_price_line = (
        f"\u041e\u0442\u043a\u0440\u044b\u0442\u0430\u044f \u0446\u0435\u043d\u0430: {format_interest_rub(open_price_minor)}"
        if open_price_minor is not None
        else "\u041e\u0442\u043a\u0440\u044b\u0442\u0430\u044f \u0446\u0435\u043d\u0430: \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u0430\u0442\u044c"
    )
    preliminary_price_line = (
        f"\u041f\u0440\u0435\u0434\u0432\u0430\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c: {format_interest_rub(preliminary_price_minor)}"
        if preliminary_price_minor is not None
        else "\u041f\u0440\u0435\u0434\u0432\u0430\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c: \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u0430\u0442\u044c"
    )

    lines = [
        f"\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435! \u041c\u0435\u043d\u044f \u0437\u0430\u0438\u043d\u0442\u0435\u0440\u0435\u0441\u043e\u0432\u0430\u043b\u0430 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f \u00ab{category_name}\u00bb.",
        "",
        "\u0425\u043e\u0447\u0443 \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u044c \u0431\u0440\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f:",
        f"\u041f\u0435\u0440\u0438\u043e\u0434: {format_selected_booking_period(checkin=period_start, checkout=period_end)}",
        f"\u0422\u0430\u0440\u0438\u0444: {tariff_label(tariff_name)}",
        "",
        open_price_line,
        "",
        preliminary_price_line,
        "",
        "\u0413\u043e\u0441\u0442\u0438:",
        *guest_lines,
    ]
    if discount_lines:
        lines.extend(["", "\u0421\u043a\u0438\u0434\u043a\u0438:", *discount_lines])
    lines.extend(["", "\u041f\u043e\u0434\u0441\u043a\u0430\u0436\u0438\u0442\u0435, \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430, \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e\u0441\u0442\u044c \u0438 \u0443\u0441\u043b\u043e\u0432\u0438\u044f \u0431\u0440\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f."])
    return "\n".join(lines)


def tariff_label(tariff: str) -> str:
    key = tariff.strip().lower()
    if key == "breakfast":
        return "\u0422\u043e\u043b\u044c\u043a\u043e \u0437\u0430\u0432\u0442\u0440\u0430\u043a\u0438"
    if key == "fullpansion":
        return "\u041f\u043e\u043b\u043d\u044b\u0439 \u043f\u0430\u043d\u0441\u0438\u043e\u043d"
    return tariff


def format_interest_date(value: date) -> str:
    return format_ui_date(value)


def format_interest_rub(value_minor: int) -> str:
    rub = Decimal(value_minor) / Decimal("100")
    if rub == rub.to_integral():
        return f"{int(rub):,}".replace(",", " ") + " \u20bd"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " \u20bd"
