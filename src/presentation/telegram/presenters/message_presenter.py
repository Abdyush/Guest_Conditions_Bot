from __future__ import annotations

from datetime import date

from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote


def _fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%y")


def _rub_from_minor(amount_minor: int) -> str:
    return f"{amount_minor / 100:.2f}"


def render_best_periods(*, guest_id: str, group_id: str, picks: list[PeriodPickDTO]) -> str:
    if not picks:
        return "К сожалению, по текущей группе, данных не собрано."

    lines: list[str] = [f"Лучшие периоды для {group_id}:", ""]
    for idx, pick in enumerate(picks, start=1):
        lines.append(
            f"{idx}. {_fmt_date(pick.start_date)}-{_fmt_date(pick.end_date_inclusive)} | "
            f"{pick.tariff_code} | рынок {pick.old_price_per_night.amount_minor / 100:.2f} ₽/сутки | "
            f"ваша {pick.new_price_per_night.amount_minor / 100:.2f} ₽/сутки"
        )
    return "\n".join(lines)


def render_period_quotes(
    *,
    guest_id: str,
    run_id: str,
    period_start: str,
    period_end: str,
    quotes: list[PeriodQuote],
    last_room_dates_by_category: dict[str, list[date]],
) -> str:
    if not quotes:
        return f"Нет вариантов на период {period_start} - {period_end}."

    grouped: dict[str, list[PeriodQuote]] = {}
    for quote in quotes:
        grouped.setdefault(quote.category_name, []).append(quote)

    lines: list[str] = [f"Варианты на период {period_start} - {period_end}:", ""]
    for category_name, category_quotes in grouped.items():
        lines.append(category_name)
        for quote in category_quotes:
            lines.append(
                f"- {quote.tariff}: рынок {_rub_from_minor(quote.total_old_minor)} ₽/сутки, "
                f"ваша {_rub_from_minor(quote.total_new_minor)} ₽/сутки"
            )

        last_dates = last_room_dates_by_category.get(category_name, [])
        if last_dates:
            formatted = ", ".join(sorted(d.isoformat() for d in last_dates))
            lines.append(f"  Даты последнего номера: {formatted}")
        lines.append("")

    return "\n".join(lines).strip()
