from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote


def _format_minor(value: int) -> str:
    return f"{(value / 100):.2f} RUB"


def _format_rub(value_minor: int) -> str:
    return f"{(value_minor / 100):.2f}"


def _format_date_ru(value) -> str:
    return value.strftime("%d.%m.%y")


def _tariff_label(tariff: str) -> str:
    key = tariff.strip().lower()
    if key == "breakfast":
        return "Только завтраки"
    if key == "fullpansion":
        return "Только полный пансион"
    return tariff


def _format_percent_text(raw: str | None) -> str:
    if not raw:
        return "—"
    cleaned = raw.strip().replace("%", "")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return raw
    if value <= Decimal("1"):
        value = value * Decimal("100")
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def render_best_periods(*, guest_id: str, group_id: str, picks: list[PeriodPickDTO]) -> str:
    if not picks:
        return f"Guest {guest_id}: no periods found for group {group_id}."

    blocks: list[str] = []
    for pick in picks:
        status_text = "—"
        if pick.applied_bank_status and pick.applied_bank_percent is not None:
            status_text = f"{_bank_label(pick.applied_bank_status.value)}, {_format_decimal_percent(pick.applied_bank_percent)}"
        elif pick.applied_loyalty_status and pick.applied_loyalty_percent:
            status_text = f"Программа лояльности ({pick.applied_loyalty_status}), {_format_percent_text(pick.applied_loyalty_percent)}"

        offer_text = pick.offer_title or "-"
        if offer_text != "-" and pick.offer_repr:
            offer_text = f"{offer_text}, {_format_percent_text(pick.offer_repr)}"

        blocks.append(
            "\n".join(
                [
                    f"{_format_date_ru(pick.start_date)} - {_format_date_ru(pick.end_date_inclusive)}",
                    f"{pick.category_name}",
                    f'Тариф: "{_tariff_label(pick.tariff_code)}"',
                    f"Ваша Цена за сутки {_format_rub(pick.new_price_per_night.amount_minor)} рублей",
                    "",
                    f"Открытая цена за сутки: {_format_rub(pick.old_price_per_night.amount_minor)} рублей",
                    "Примененные скидки:",
                    f"Специальное предложение: {offer_text}",
                    f"Статус: {status_text}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _bank_label(value: str) -> str:
    mapping = {
        "SBER_PREMIER": "Сбер Премьер",
        "SBER_FIRST": "Сбер1",
        "SBER_PRIVATE": "Сбер Прайвет",
    }
    return mapping.get(value, value)


def _format_decimal_percent(value: Decimal) -> str:
    text = f"{(value * Decimal('100')):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def render_period_quotes(
    *,
    guest_id: str,
    run_id: str,
    period_start: str,
    period_end: str,
    quotes: list[PeriodQuote],
    last_room_dates_by_category: dict[str, list[date]] | None = None,
) -> str:
    if not run_id:
        return "No data in matches_run. Run pipeline first."
    if not quotes:
        return f"Guest {guest_id}: no options for period {period_start} - {period_end}."

    quotes_sorted = sorted(
        quotes,
        key=lambda q: (q.category_name, q.from_date, q.to_date, q.tariff),
    )
    grouped: dict[tuple[str, object, object, int], list[PeriodQuote]] = {}
    for q in quotes_sorted:
        key = (q.category_name, q.from_date, q.to_date, q.nights)
        grouped.setdefault(key, []).append(q)

    blocks: list[str] = []
    for (category_name, from_date, to_date, nights), group_quotes in grouped.items():
        lines: list[str] = [
            category_name,
            f"{_format_date_ru(from_date)} - {_format_date_ru(to_date)}, {nights} ночи",
            "",
        ]

        for q in sorted(group_quotes, key=lambda x: x.tariff):
            lines.extend(
                [
                    f'Тариф: "{_tariff_label(q.tariff)}"',
                    f"Цена открытого рынка: {_format_rub(q.total_old_minor)} рублей за период",
                    f"Ваша цена: {_format_rub(q.total_new_minor)} рублей за период",
                    "",
                ]
            )

        offer_scope = "—"
        offer_name = "—"
        offer_percent = "—"
        status_name = "—"
        status_percent = "—"

        for q in group_quotes:
            if q.offer_id:
                offer_scope = (
                    "Весь период"
                    if q.applied_from == q.from_date and q.applied_to == q.to_date
                    else f"{_format_date_ru(q.applied_from)} - {_format_date_ru(q.applied_to)}"
                )
                offer_name = q.offer_title or q.offer_id
                offer_percent = _format_percent_text(q.offer_repr)
                break

        for q in group_quotes:
            if q.bank_status and q.bank_percent:
                status_name = f"сбер ({q.bank_status})"
                status_percent = _format_percent_text(q.bank_percent)
                break
            if q.loyalty_status and q.loyalty_percent:
                status_name = f"программа лояльности ({q.loyalty_status})"
                status_percent = _format_percent_text(q.loyalty_percent)
                break

        lines.extend(
            [
                "Примененные скидки:",
                f'Специальное предложение: "{offer_scope}", "{offer_name}", размер скидки {offer_percent}',
                f"Статус: {status_name}, размер скидки {status_percent}",
            ]
        )
        last_room_dates = (last_room_dates_by_category or {}).get(category_name, [])
        if last_room_dates:
            joined = ", ".join(_format_date_ru(x) for x in sorted(set(last_room_dates)))
            lines.extend(["", f"Последние номера: {joined}"])
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
