from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from src.application.dto.matched_date_record import MatchedDateRecord


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



def render_available_period_details(*, category_name: str, period: AvailablePeriod, last_room_dates: list[date]) -> str:
    lines = [
        category_name,
        f"{format_date(period.display_start)} – {format_date(period.end)}",
        "",
    ]

    rows_by_tariff: dict[str, MatchedDateRecord] = {}
    for row in period.rows:
        key = row.tariff.strip().lower()
        current = rows_by_tariff.get(key)
        if current is None or row.new_price_minor < current.new_price_minor:
            rows_by_tariff[key] = row

    for tariff_key in _tariff_sort_keys(rows_by_tariff.keys()):
        row = rows_by_tariff[tariff_key]
        benefit_minor = row.old_price_minor - row.new_price_minor
        lines.extend(
            [
                f"Тариф: {tariff_label(row.tariff)}",
                f"Цена открытого рынка: {format_rub(row.old_price_minor)}/сутки",
                f"Ваша цена: {format_rub(row.new_price_minor)}/сутки",
                f"Ваша выгода: {format_rub(benefit_minor)}/сутки",
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
            status_name = f"Статус в Сбере: {row.bank_status}"
            status_percent = format_percent(row.bank_percent)
            break
        if row.loyalty_status and row.loyalty_percent is not None:
            status_name = f"Программа лояльности: {str(row.loyalty_status).capitalize()}"
            status_percent = format_percent(row.loyalty_percent)
            break

    lines.extend(
        [
            "Применённые скидки:",
            f"• Специальное предложение: «{offer_name}» — {offer_percent}" if offer_name != "—" else "• Специальное предложение: —",
            f"• {status_name} — {status_percent}" if status_name != "—" else "• Статус: —",
        ]
    )
    if last_room_dates:
        last_room_line = ", ".join(format_date(x) for x in sorted(set(last_room_dates)))
        lines.extend(["", f"Последние номера: {last_room_line}"])
    return "\n".join(lines).strip()



def render_available_offer_text(*, offer_title: str | None, offer_text: str) -> str:
    title = offer_title or "Специальное предложение"
    return f"Специальное предложение: «{title}»\n\n{offer_text.strip()}"



def render_available_request_calendar_prompt(*, category_name: str) -> str:
    return f"{category_name}\n\nВыберите желаемый период проживания."



def render_available_request_tariff_prompt(*, category_name: str, checkin: date, checkout: date) -> str:
    return (
        f"{category_name}\n"
        f"Период {format_date(checkin)} – {format_date(checkout)}\n\n"
        "Выберите тариф."
    )



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
    guest_lines = [f"Взрослые: {adults}"]
    if children_4_13 > 0:
        guest_lines.append(f"Дети (4–13 лет): {children_4_13}")
    if infants_0_3 > 0:
        guest_lines.append(f"Дети (0–3 лет): {infants_0_3}")

    discount_lines: list[str] = []
    if loyalty_status:
        discount_lines.append(f"статус в пл: {loyalty_status.lower()}")
    for offer_start, offer_end, offer_title in special_offers:
        discount_lines.append(
            f'спецпредложение: {format_date(offer_start)} – {format_date(offer_end)} "{offer_title}"'
        )

    open_price_line = (
        f"Открытая цена: {format_rub(open_price_minor)}"
        if open_price_minor is not None
        else "Открытая цена: не удалось рассчитать"
    )
    preliminary_price_line = (
        f"Предварительная стоимость: {format_rub(preliminary_price_minor)}"
        if preliminary_price_minor is not None
        else "Предварительная стоимость: не удалось рассчитать"
    )

    lines = [
        f"Здравствуйте! Меня заинтересовала категория «{category_name}».",
        "",
        "Хочу уточнить возможность бронирования:",
        f"Период: {format_date(period_start)} – {format_date(period_end)}",
        f"Тариф: {tariff_label}",
        "",
        open_price_line,
        "",
        preliminary_price_line,
        "",
        "Гости:",
        *guest_lines,
    ]
    if discount_lines:
        lines.extend(["", "Скидки:", *discount_lines])
    lines.extend(["", "Подскажите, пожалуйста, доступность и условия бронирования."])
    return "\n".join(lines)



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



def format_period_button_label(*, start: date, end: date, price_minor: int) -> str:
    return f"{format_date(start)} - {format_date(end)}, {minor_to_rub(price_minor):.2f} рублей в сутки"



def format_breakfast_period_button_label(*, start: date, end: date, price_minor: int) -> str:
    return f"{format_date(start)}–{format_date(end)} • {format_rub(price_minor)}/сутки"



def format_date(value: date) -> str:
    return value.strftime("%d.%m.%y")



def minor_to_rub(value: int) -> float:
    return value / 100



def format_rub(value_minor: int) -> str:
    rub = Decimal(value_minor) / Decimal("100")
    if rub == rub.to_integral():
        return f"{int(rub):,}".replace(",", " ") + " ₽"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " ₽"



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

