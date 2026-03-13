from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple

from src.application.dto.matched_date_record import MatchedDateRecord


class AvailablePeriod(NamedTuple):
    start: date
    end: date
    min_new_price_minor: int
    rows: list[MatchedDateRecord]


def render_available_category_periods(*, category_name: str, periods: list[AvailablePeriod]) -> str:
    if not periods:
        return f"{category_name}\n\nПериоды проживания:\nНет данных."
    return f"{category_name}\n\nПериоды проживания:"


def render_available_period_details(*, category_name: str, period: AvailablePeriod, last_room_dates: list[date]) -> str:
    lines = [
        category_name,
        f"{format_date(period.start)} - {format_date(period.end)}",
        "",
    ]

    rows_by_tariff: dict[str, MatchedDateRecord] = {}
    for row in period.rows:
        key = row.tariff.strip().lower()
        current = rows_by_tariff.get(key)
        if current is None or row.new_price_minor < current.new_price_minor:
            rows_by_tariff[key] = row

    for tariff_key in sorted(rows_by_tariff.keys()):
        row = rows_by_tariff[tariff_key]
        lines.extend(
            [
                f'Тариф: "{tariff_label(row.tariff)}"',
                f"Цена открытого рынка: {minor_to_rub(row.old_price_minor):.2f} рублей в сутки",
                f"Ваша цена: {minor_to_rub(row.new_price_minor):.2f} рублей в сутки",
                "",
            ]
        )

    offer_name = "—"
    offer_percent = "—"
    status_name = "—"
    status_percent = "—"
    for row in period.rows:
        if row.offer_title or row.offer_repr or row.offer_id:
            offer_name = row.offer_title or row.offer_id or "—"
            offer_percent = row.offer_repr or "—"
            break
    for row in period.rows:
        if row.bank_status and row.bank_percent is not None:
            status_name = f"сбер ({row.bank_status})"
            status_percent = format_percent(row.bank_percent)
            break
        if row.loyalty_status and row.loyalty_percent is not None:
            status_name = f"программа лояльности ({row.loyalty_status})"
            status_percent = format_percent(row.loyalty_percent)
            break

    lines.extend(
        [
            "Примененные скидки:",
            f'Специальное предложение: "{offer_name}", размер скидки {offer_percent}',
            f"Статус: {status_name}, размер скидки {status_percent}",
        ]
    )
    if last_room_dates:
        last_room_line = ", ".join(format_date(x) for x in sorted(set(last_room_dates)))
        lines.extend(["", f"Последние номера: {last_room_line}"])
    return "\n".join(lines).strip()


def build_available_periods(*, rows: list[MatchedDateRecord]) -> list[AvailablePeriod]:
    grouped: dict[tuple[date, date], list[MatchedDateRecord]] = {}
    for row in rows:
        start = row.date
        end = row.period_end or row.date
        grouped.setdefault((start, end), []).append(row)

    periods: list[AvailablePeriod] = []
    for (start, end), group_rows in grouped.items():
        min_new_price_minor = min(r.new_price_minor for r in group_rows)
        periods.append(
            AvailablePeriod(
                start=start,
                end=end,
                min_new_price_minor=min_new_price_minor,
                rows=sorted(group_rows, key=lambda r: (r.tariff, r.new_price_minor)),
            )
        )
    periods.sort(key=lambda p: (p.start, p.end, p.min_new_price_minor))
    return periods


def format_period_button_label(*, start: date, end: date, price_minor: int) -> str:
    return f"{format_date(start)} - {format_date(end)}, {minor_to_rub(price_minor):.2f} рублей в сутки"


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%y")


def minor_to_rub(value: int) -> float:
    return value / 100


def tariff_label(tariff: str) -> str:
    key = tariff.strip().lower()
    if key == "breakfast":
        return "Только завтраки"
    if key == "fullpansion":
        return "Только полный пансион"
    return tariff


def format_percent(value: Decimal) -> str:
    raw = f"{value * Decimal('100'):.2f}"
    trimmed = raw.rstrip("0").rstrip(".")
    return f"{trimmed}%"
