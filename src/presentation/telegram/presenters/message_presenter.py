from __future__ import annotations

from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote


def _format_minor(value: int) -> str:
    return f"{(value / 100):.2f} RUB"


def render_best_periods(*, guest_id: str, group_id: str, picks: list[PeriodPickDTO]) -> str:
    if not picks:
        return f"Guest {guest_id}: no periods found for group {group_id}."

    lines = [f"Guest {guest_id}. Best periods for group {group_id}:"]
    for idx, pick in enumerate(picks, start=1):
        discount_parts: list[str] = []
        if pick.offer_title:
            offer_text = pick.offer_title
            if pick.offer_repr:
                offer_text = f"{offer_text} ({pick.offer_repr})"
            if pick.offer_min_nights is not None:
                offer_text = f"{offer_text}, min_nights={pick.offer_min_nights}"
            discount_parts.append(f"offer: {offer_text}")
        if pick.applied_loyalty_status and pick.applied_loyalty_percent:
            discount_parts.append(f"loyalty: {pick.applied_loyalty_status} {pick.applied_loyalty_percent}")
        if pick.applied_bank_status and pick.applied_bank_percent:
            discount_parts.append(f"bank: {pick.applied_bank_status.value} {pick.applied_bank_percent}")
        discounts = ", ".join(discount_parts) if discount_parts else "-"

        lines.append(
            f"{idx}. {pick.start_date.isoformat()} - {pick.end_date_inclusive.isoformat()} "
            f"({pick.nights} nights) | {pick.category_name} | {pick.tariff_code} | "
            f"{_format_minor(pick.new_price_per_night.amount_minor)} per night | {discounts}"
        )
    return "\n".join(lines)


def render_period_quotes(
    *,
    guest_id: str,
    run_id: str,
    period_start: str,
    period_end: str,
    quotes: list[PeriodQuote],
) -> str:
    if not run_id:
        return "No data in matches_run. Run pipeline first."
    if not quotes:
        return f"Guest {guest_id}: no options for period {period_start} - {period_end}."

    lines = [f"Guest {guest_id}. Quotes for {period_start} - {period_end}. run_id={run_id}"]
    for idx, q in enumerate(quotes, start=1):
        discount_parts: list[str] = []
        if q.offer_id:
            offer_label = q.offer_title or q.offer_id
            discount_parts.append(
                f"offer: {offer_label} ({q.applied_from.isoformat()} - {q.applied_to.isoformat()})"
            )
        if q.loyalty_status and q.loyalty_percent:
            discount_parts.append(f"loyalty: {q.loyalty_status} {q.loyalty_percent}")
        if q.bank_status and q.bank_percent:
            discount_parts.append(f"bank: {q.bank_status} {q.bank_percent}")
        discounts = ", ".join(discount_parts) if discount_parts else "-"

        lines.append(
            f"{idx}. {q.category_name} | {q.group_id} | {q.tariff} | nights={q.nights} | "
            f"old={_format_minor(q.total_old_minor)} | new={_format_minor(q.total_new_minor)} | {discounts}"
        )
    return "\n".join(lines)

