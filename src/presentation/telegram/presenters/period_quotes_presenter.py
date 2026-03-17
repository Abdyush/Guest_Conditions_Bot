from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from src.application.dto.period_quote import PeriodQuote


def render_period_quotes_groups_prompt() -> str:
    return "Выберите группу категорий, чтобы посмотреть цены на нужный период."


def render_period_quotes_calendar_prompt() -> str:
    return "Выберите даты проживания: сначала дату заезда, затем дату выезда."


def render_period_quotes_category_prompt(*, period_start, period_end) -> str:
    return f"Вы выбрали период: {format_date(period_start)} - {format_date(period_end)}.\nТеперь выберите категорию."


def render_period_quotes_flow_hint() -> str:
    return "Сейчас открыт сценарий «Цены на период». Используйте кнопки этого сценария, календарь и кнопку «Главное меню»."


def render_period_quotes_empty(*, period_start, period_end) -> str:
    return (
        f"На период {format_date(period_start)} - {format_date(period_end)} сейчас нет подходящих вариантов.\n"
        "Попробуйте выбрать другие даты."
    )


def render_period_quote_card(
    *,
    category_name: str,
    period_start,
    period_end,
    quotes: list[PeriodQuote],
    last_room_dates: list,
) -> str:
    lines = [
        category_name,
        f"{format_date(period_start)} - {format_date(period_end)}",
        "",
    ]

    for quote in _sorted_quotes(quotes):
        lines.extend(_render_tariff_block(quote))
        lines.append("")

    discount_lines = _render_discount_lines(quotes)
    if discount_lines:
        lines.append("Применённые скидки:")
        lines.extend(discount_lines)
        lines.append("")

    if last_room_dates:
        formatted_dates = ", ".join(format_date(value) for value in sorted(set(last_room_dates)))
        lines.append(f"Последние номера на даты: {formatted_dates}")

    return "\n".join(line for line in lines if line is not None).strip()


def render_period_quote_offer_text(*, offer_title: str | None, offer_text: str) -> str:
    title = offer_title or "Специальное предложение"
    return f"Специальное предложение: «{title}»\n\n{offer_text}".strip()


def format_date(value) -> str:
    return value.strftime("%d.%m.%y")


def _render_tariff_block(quote: PeriodQuote) -> list[str]:
    old_per_night = _minor_per_night(quote.total_old_minor, quote.nights)
    new_per_night = _minor_per_night(quote.total_new_minor, quote.nights)
    benefit = old_per_night - new_per_night

    lines = [f"Тариф: {tariff_label(quote.tariff)}"]
    if quote.applied_from != quote.from_date or quote.applied_to != quote.to_date:
        lines.append(f"Период действия тарифа: {format_date(quote.applied_from)} - {format_date(quote.applied_to)}")
    lines.extend(
        [
            f"Цена открытого рынка: {format_money(old_per_night)} ₽/сутки",
            f"Ваша цена: {format_money(new_per_night)} ₽/сутки",
            f"Ваша выгода: {format_money(benefit)} ₽/сутки",
        ]
    )
    return lines


def _render_discount_lines(quotes: Iterable[PeriodQuote]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for quote in quotes:
        if quote.offer_title or quote.offer_repr:
            label = f"• Специальное предложение: «{quote.offer_title or 'Без названия'}»"
            if quote.offer_repr:
                label += f" - {quote.offer_repr}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
        if quote.bank_status and quote.bank_percent:
            label = f"• Статус в Сбере: {quote.bank_status} - {quote.bank_percent}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
        elif quote.loyalty_status and quote.loyalty_percent:
            status = quote.loyalty_status.capitalize()
            label = f"• Программа лояльности: {status} - {quote.loyalty_percent}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
    return lines


def _minor_per_night(total_minor: int, nights: int) -> Decimal:
    if nights <= 0:
        return Decimal("0")
    return (Decimal(total_minor) / Decimal("100") / Decimal(nights)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_money(amount: Decimal) -> str:
    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized == normalized.to_integral():
        return f"{int(normalized):,}".replace(",", " ")
    return f"{normalized:,.2f}".replace(",", " ")


def tariff_label(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "breakfast":
        return "Только завтраки"
    if normalized == "fullpansion":
        return "Полный пансион"
    return value


def _sorted_quotes(quotes: list[PeriodQuote]) -> list[PeriodQuote]:
    order = {"breakfast": 0, "fullpansion": 1}
    return sorted(quotes, key=lambda item: (order.get(item.tariff.strip().lower(), 99), item.applied_from, item.applied_to))
