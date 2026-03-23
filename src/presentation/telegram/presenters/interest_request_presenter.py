from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.presentation.telegram.presenters.booking_period import (
    format_selected_booking_period,
    format_ui_date,
)


def render_interest_request_calendar_prompt(*, category_name: str) -> str:
    return f"{category_name}\n\nВыберите желаемый период проживания."


def render_interest_request_tariff_prompt(*, category_name: str, checkin: date, checkout: date) -> str:
    return (
        f"{category_name}\n"
        f"Период {format_selected_booking_period(checkin=checkin, checkout=checkout)}\n\n"
        "Выберите тариф."
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
    lines = [
        "Здравствуйте!",
        "",
        f"Интересует категория «{category_name}».",
        "",
        f"Период: {format_selected_booking_period(checkin=period_start, checkout=period_end)}",
        f"Тариф: {tariff_label(tariff_name)}",
        "",
        "Стоимость:",
        f"• Цена на открытом рынке — {_format_price_line(open_price_minor)}",
        f"• Предварительная цена — {_format_price_line(preliminary_price_minor)}",
        "",
        *_render_guests_block(
            adults=adults,
            children_4_13=children_4_13,
            infants_0_3=infants_0_3,
        ),
    ]

    discount_lines = _render_discount_lines(
        loyalty_status=loyalty_status,
        special_offers=special_offers,
        period_start=period_start,
        period_end=period_end,
    )
    if discount_lines:
        lines.extend(["", "С учётом:", *discount_lines])

    lines.extend(["", "Подскажите, пожалуйста, доступность и актуальные условия бронирования."])
    return "\n".join(lines)


def tariff_label(tariff: str) -> str:
    key = tariff.strip().lower()
    if key == "breakfast":
        return "только завтраки"
    if key == "fullpansion":
        return "полный пансион"
    return tariff


def format_interest_date(value: date) -> str:
    return format_ui_date(value)


def format_interest_rub(value_minor: int) -> str:
    rub = Decimal(value_minor) / Decimal("100")
    if rub == rub.to_integral():
        return f"{int(rub):,}".replace(",", " ") + " ₽"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def _format_price_line(value_minor: int | None) -> str:
    if value_minor is None:
        return "не удалось рассчитать"
    return format_interest_rub(value_minor)


def _render_guests_block(*, adults: int, children_4_13: int, infants_0_3: int) -> list[str]:
    if adults == 1 and children_4_13 == 0 and infants_0_3 == 0:
        return ["Гость: 1 взрослый"]
    return [
        "Гости:",
        f"• Взрослые: {adults}",
        f"• Дети 4–17: {children_4_13}",
        f"• Дети 0–3: {infants_0_3}",
    ]


def _render_discount_lines(
    *,
    loyalty_status: str | None,
    special_offers: list[tuple[date, date, str]],
    period_start: date,
    period_end: date,
) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    if loyalty_status:
        label = f"• программа лояльности — {loyalty_status.capitalize()}"
        lines.append(label)
        seen.add(label)

    for offer_start, offer_end, offer_title in special_offers:
        if _same_period(
            offer_start=offer_start,
            offer_end=offer_end,
            period_start=period_start,
            period_end=period_end,
        ):
            label = f"• спецпредложение «{offer_title}»"
        else:
            label = (
                f"• спецпредложение {format_selected_booking_period(checkin=offer_start, checkout=offer_end)} "
                f"«{offer_title}»"
            )
        if label not in seen:
            lines.append(label)
            seen.add(label)

    return lines


def _same_period(*, offer_start: date, offer_end: date, period_start: date, period_end: date) -> bool:
    return offer_start == period_start and offer_end == period_end
