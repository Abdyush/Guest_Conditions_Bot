from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

from src.application.dto.matched_date_record import MatchedDateRecord
from src.presentation.telegram.presenters.booking_period import format_booking_period, format_ui_date
from src.presentation.telegram.presenters.interest_request_presenter import (
    render_interest_request_calendar_prompt,
    render_interest_request_message,
    render_interest_request_tariff_prompt,
)


@dataclass(frozen=True, slots=True)
class AvailableCategoryGroup:
    label: str
    categories: list[str]


class AvailablePeriod(NamedTuple):
    start: date
    display_start: date
    end: date
    min_new_price_minor: int
    rows: list[MatchedDateRecord]


@dataclass(frozen=True, slots=True)
class AvailableBreakfastPeriod:
    start: date
    display_start: date
    end: date
    button_price_minor: int
    rows: list[MatchedDateRecord]


@dataclass(frozen=True, slots=True)
class AvailablePriceGroup:
    price_minor: int
    period_indices: list[int]


def build_available_groups(*, category_groups: list[tuple[str, str]]) -> list[AvailableCategoryGroup]:
    grouped: dict[str, set[str]] = {}
    for category_name, group_id in category_groups:
        bucket = _group_bucket_label(group_id=group_id, category_name=category_name)
        grouped.setdefault(bucket, set()).add(category_name)

    out = [
        AvailableCategoryGroup(label=label, categories=sorted(categories))
        for label, categories in grouped.items()
    ]
    order = {"Делюкс": 0, "Люкс": 1, "Вилла": 2, "Апартаменты": 3}
    out.sort(key=lambda item: (order.get(item.label, 100), item.label))
    return out


def render_available_groups_prompt() -> str:
    return "Выберите группу категорий, чтобы посмотреть доступные варианты и цены."


def render_available_categories_prompt(*, group_label: str) -> str:
    return f"{group_label}\n\nВыберите категорию."


def render_available_periods_prompt(*, category_name: str, periods: list[AvailableBreakfastPeriod]) -> str:
    if not periods:
        return f"{category_name}\n\nВыберите период проживания.\nНет доступных периодов."
    return f"{category_name}\n\nВыберите период проживания."


def render_available_price_groups_prompt(*, category_name: str, groups: list[AvailablePriceGroup]) -> str:
    if not groups:
        return f"{category_name}\n\nВыберите стоимость проживания.\nНет доступных периодов."
    return f"{category_name}\n\nВыберите стоимость проживания."


def render_available_price_periods_prompt(
    *,
    category_name: str,
    price_minor: int,
    periods: list[AvailableBreakfastPeriod],
) -> str:
    if not periods:
        return f"{category_name}\n\nДля цены {format_rub(price_minor)}/сутки нет доступных периодов."
    return f"{category_name}\n\nЦена: {format_rub(price_minor)}/сутки\nВыберите период проживания."


def render_available_period_details(*, category_name: str, period: AvailablePeriod, last_room_dates: list[date]) -> str:
    rows_by_tariff: dict[str, MatchedDateRecord] = {}
    for row in period.rows:
        key = row.tariff.strip().lower()
        current = rows_by_tariff.get(key)
        if current is None or row.new_price_minor < current.new_price_minor:
            rows_by_tariff[key] = row

    blocks = [
        f"🏡 {category_name}",
        f"📅 {format_booking_period(start_date=period.display_start, end_date_inclusive=period.end, separator=' – ')}",
    ]

    tariff_blocks: list[str] = []
    for tariff_key in _tariff_sort_keys(rows_by_tariff.keys()):
        row = rows_by_tariff[tariff_key]
        benefit_minor = row.old_price_minor - row.new_price_minor
        tariff_blocks.append(
            "\n".join(
                [
                    f"🍽 {tariff_label(row.tariff)}",
                    f"Цена рынка: {format_price_minor(row.old_price_minor)} ₽/сутки",
                    f"Ваша цена: {format_price_minor(row.new_price_minor)} ₽/сутки",
                    f"Выгода: {format_price_minor(benefit_minor)} ₽/сутки",
                ]
            )
        )
    if tariff_blocks:
        blocks.append("\n\n".join(tariff_blocks))

    discount_lines = _render_available_discount_lines(period.rows)
    if discount_lines:
        blocks.append("\n".join(["✨ Применённые скидки", *discount_lines]))

    if last_room_dates:
        last_room_line = ", ".join(format_date(x) for x in sorted(set(last_room_dates)))
        blocks.append("\n".join(["⚠️ Остались последние даты", last_room_line]))

    return "\n\n".join(blocks).strip()


def render_available_offer_text(*, offer_title: str | None, offer_text: str) -> str:
    title = offer_title or "Специальное предложение"
    return f"Специальное предложение: «{title}»\n\n{offer_text.strip()}"


def render_available_request_calendar_prompt(*, category_name: str) -> str:
    return render_interest_request_calendar_prompt(category_name=category_name)


def render_available_request_tariff_prompt(*, category_name: str, checkin: date, checkout: date) -> str:
    return render_interest_request_tariff_prompt(category_name=category_name, checkin=checkin, checkout=checkout)


def render_available_interest_message(
    *,
    category_name: str,
    period_start: date,
    period_end: date,
    tariff_label: str,
    open_price_minor: int | None,
    preliminary_price_minor: int | None,
    adults: int,
    children_4_13: int,
    infants_0_3: int,
    loyalty_status: str | None,
    special_offers: list[tuple[date, date, str]],
) -> str:
    return render_interest_request_message(
        category_name=category_name,
        period_start=period_start,
        period_end=period_end,
        tariff_name=tariff_label,
        open_price_minor=open_price_minor,
        preliminary_price_minor=preliminary_price_minor,
        adults=adults,
        children_4_13=children_4_13,
        infants_0_3=infants_0_3,
        loyalty_status=loyalty_status,
        special_offers=special_offers,
    )


def render_available_request_text(
    *,
    category_name: str,
    checkin: date,
    checkout: date,
    tariff: str,
    open_price_minor: int | None,
    preliminary_price_minor: int | None,
    adults: int,
    children_4_13: int,
    infants_0_3: int,
    loyalty_status: str | None,
    special_offers: list[tuple[date, date, str]],
) -> str:
    return render_available_interest_message(
        category_name=category_name,
        period_start=checkin,
        period_end=checkout,
        tariff_label=tariff,
        open_price_minor=open_price_minor,
        preliminary_price_minor=preliminary_price_minor,
        adults=adults,
        children_4_13=children_4_13,
        infants_0_3=infants_0_3,
        loyalty_status=loyalty_status,
        special_offers=special_offers,
    )


def render_available_category_periods(*, category_name: str, periods: list[AvailablePeriod]) -> str:
    if not periods:
        return f"{category_name}\n\nПериоды проживания:\nНет данных."
    return f"{category_name}\n\nПериоды проживания:"


def build_available_periods(*, rows: list[MatchedDateRecord]) -> list[AvailablePeriod]:
    today = date.today()
    grouped: dict[tuple[date, date], list[MatchedDateRecord]] = {}
    for row in rows:
        start = row.date
        end = row.period_end or row.date
        grouped.setdefault((start, end), []).append(row)

    periods: list[AvailablePeriod] = []
    for (start, end), group_rows in grouped.items():
        display_start = max(start, today)
        if display_start > end:
            continue
        min_new_price_minor = min(r.new_price_minor for r in group_rows)
        periods.append(
            AvailablePeriod(
                start=start,
                display_start=display_start,
                end=end,
                min_new_price_minor=min_new_price_minor,
                rows=sorted(group_rows, key=lambda r: (r.tariff, r.new_price_minor)),
            )
        )
    periods.sort(key=lambda p: (p.start, p.end, p.min_new_price_minor))
    return periods


def build_available_breakfast_periods(*, rows: list[MatchedDateRecord]) -> list[AvailableBreakfastPeriod]:
    today = date.today()
    grouped: dict[tuple[date, date], list[MatchedDateRecord]] = {}
    for row in rows:
        start = row.date
        end = row.period_end or row.date
        grouped.setdefault((start, end), []).append(row)

    periods: list[AvailableBreakfastPeriod] = []
    for (start, end), group_rows in grouped.items():
        display_start = max(start, today)
        if display_start > end:
            continue
        breakfast_rows = [r for r in group_rows if r.tariff.strip().lower() == "breakfast"]
        source_rows = breakfast_rows or group_rows
        button_price_minor = min(r.new_price_minor for r in source_rows)
        periods.append(
            AvailableBreakfastPeriod(
                start=start,
                display_start=display_start,
                end=end,
                button_price_minor=button_price_minor,
                rows=sorted(group_rows, key=lambda r: (r.tariff, r.new_price_minor)),
            )
        )
    periods.sort(key=lambda p: (p.start, p.end, p.button_price_minor))
    return periods


def build_available_price_groups(*, periods: list[AvailableBreakfastPeriod]) -> list[AvailablePriceGroup]:
    grouped: dict[int, list[int]] = {}
    for idx, period in enumerate(periods):
        grouped.setdefault(period.button_price_minor, []).append(idx)

    out = [
        AvailablePriceGroup(price_minor=price_minor, period_indices=period_indices)
        for price_minor, period_indices in grouped.items()
    ]
    out.sort(
        key=lambda item: (
            item.price_minor,
            periods[item.period_indices[0]].display_start if item.period_indices else date.max,
        )
    )
    return out


def format_period_button_label(*, start: date, end: date, price_minor: int) -> str:
    return f"{format_booking_period(start_date=start, end_date_inclusive=end, separator=' - ')}, {minor_to_rub(price_minor):.2f} рублей в сутки"


def format_breakfast_period_button_label(*, start: date, end: date, price_minor: int) -> str:
    return f"{format_booking_period(start_date=start, end_date_inclusive=end, separator='–')} • {format_rub(price_minor)}/сутки"


def format_available_price_group_button_label(*, price_minor: int, periods_count: int) -> str:
    if periods_count % 10 == 1 and periods_count % 100 != 11:
        suffix = "период"
    elif periods_count % 10 in {2, 3, 4} and periods_count % 100 not in {12, 13, 14}:
        suffix = "периода"
    else:
        suffix = "периодов"
    return f"{format_rub(price_minor)}/сутки • {periods_count} {suffix}"


def format_date(value: date) -> str:
    return format_ui_date(value)


def minor_to_rub(value: int) -> float:
    return value / 100


def format_rub(value_minor: int) -> str:
    rub = Decimal(value_minor) / Decimal("100")
    if rub == rub.to_integral():
        return f"{int(rub):,}".replace(",", " ") + " ₽"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def format_price_minor(value_minor: int) -> str:
    return format_money_amount(Decimal(value_minor) / Decimal("100"))


def tariff_label(tariff: str) -> str:
    key = tariff.strip().lower()
    if key == "breakfast":
        return "Только завтраки"
    if key == "fullpansion":
        return "Полный пансион"
    return tariff


def format_percent(value: Decimal) -> str:
    raw = f"{value * Decimal('100'):.2f}"
    trimmed = raw.rstrip("0").rstrip(".")
    return f"{trimmed}%"


def format_money_amount(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized == normalized.to_integral():
        return f"{int(normalized):,}".replace(",", " ")
    return f"{normalized:,.2f}".replace(",", " ").replace(".", ",")


def _group_bucket_label(*, group_id: str, category_name: str) -> str:
    code = group_id.strip().upper()
    category_upper = category_name.strip().upper()
    if code in {"DELUXE", "DELUXE NEW"}:
        return "Делюкс"
    if code in {"SUITE", "ROYAL SUITE", "PENTHOUSE"}:
        return "Люкс"
    if code == "VILLA" or "VILLA" in category_upper:
        return "Вилла"
    if code in {"SPA MEDICAL SUITE", "JAPANESE SUITE GARDEN"}:
        return "Апартаменты"
    return group_id.title()


def _tariff_sort_keys(keys) -> list[str]:
    order = {"breakfast": 0, "fullpansion": 1}
    return sorted(keys, key=lambda key: (order.get(key, 100), key))


def _render_available_discount_lines(rows: list[MatchedDateRecord]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    for row in rows:
        if row.offer_repr:
            offer_name = f"«{row.offer_title}»" if row.offer_title else "Спецпредложение"
            label = f"• {offer_name} — {row.offer_repr}"
            if label not in seen:
                lines.append(label)
                seen.add(label)

    for row in rows:
        if row.bank_status and row.bank_percent is not None:
            label = f"• {_format_bank_discount_name(row.bank_status)} — {format_percent(row.bank_percent)}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
                continue
        if row.loyalty_status and row.loyalty_percent is not None:
            label = f"• {str(row.loyalty_status).capitalize()} — {format_percent(row.loyalty_percent)}"
            if label not in seen:
                lines.append(label)
                seen.add(label)

    return lines


def _format_bank_discount_name(bank_status: str) -> str:
    labels = {
        "SBER_PREMIER": "СберПремьер",
        "SBER_FIRST": "СберПервый",
        "SBER_PRIVATE": "СберПрайват",
    }
    return labels.get(bank_status, bank_status)
