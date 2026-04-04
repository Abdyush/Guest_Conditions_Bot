from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from src.application.dto.period_quote import PeriodQuote
from src.presentation.telegram.presenters.available_presenter import format_price_minor
from src.presentation.telegram.presenters.booking_period import format_booking_period, format_ui_date


@dataclass(frozen=True, slots=True)
class TariffQuoteSummary:
    tariff: str
    total_old_minor: int
    total_new_minor: int


def render_period_quotes_groups_prompt() -> str:
    return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0433\u0440\u0443\u043f\u043f\u0443 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0439, \u0447\u0442\u043e\u0431\u044b \u043f\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0446\u0435\u043d\u044b \u043d\u0430 \u043d\u0443\u0436\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434."


def render_period_quotes_calendar_prompt() -> str:
    return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u0430\u0442\u044b \u043f\u0440\u043e\u0436\u0438\u0432\u0430\u043d\u0438\u044f: \u0441\u043d\u0430\u0447\u0430\u043b\u0430 \u0434\u0430\u0442\u0443 \u0437\u0430\u0435\u0437\u0434\u0430, \u0437\u0430\u0442\u0435\u043c \u0434\u0430\u0442\u0443 \u0432\u044b\u0435\u0437\u0434\u0430."


def render_period_quotes_category_prompt(*, period_start, period_end) -> str:
    return (
        f"\u0412\u044b \u0432\u044b\u0431\u0440\u0430\u043b\u0438 \u043f\u0435\u0440\u0438\u043e\u0434: "
        f"{format_booking_period(start_date=period_start, end_date_inclusive=period_end, separator=' - ')}.\n"
        "\u0422\u0435\u043f\u0435\u0440\u044c \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e."
    )


def render_period_quotes_flow_hint() -> str:
    return (
        "\u0421\u0435\u0439\u0447\u0430\u0441 \u043e\u0442\u043a\u0440\u044b\u0442 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439 "
        "\u00ab\u0426\u0435\u043d\u044b \u043d\u0430 \u043f\u0435\u0440\u0438\u043e\u0434\u00bb. "
        "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0438 \u044d\u0442\u043e\u0433\u043e \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u044f, "
        "\u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c \u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u00ab\u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e\u00bb."
    )


def render_period_quotes_empty(*, period_start, period_end) -> str:
    return (
        f"\u041d\u0430 \u043f\u0435\u0440\u0438\u043e\u0434 "
        f"{format_booking_period(start_date=period_start, end_date_inclusive=period_end, separator=' - ')} "
        "\u0441\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u0442 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u0445 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u043e\u0432.\n"
        "\u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0432\u044b\u0431\u0440\u0430\u0442\u044c \u0434\u0440\u0443\u0433\u0438\u0435 \u0434\u0430\u0442\u044b."
    )


def render_period_quote_card(
    *,
    category_name: str,
    period_start,
    period_end,
    quotes: list[PeriodQuote],
    last_room_dates: list,
) -> str:
    return _render_period_quote_card_blocks(
        category_name=category_name,
        period_start=period_start,
        period_end=period_end,
        quotes=quotes,
        last_room_dates=last_room_dates,
    )


def render_best_period_quote_card(
    *,
    category_name: str,
    period_start,
    period_end,
    quotes: list[PeriodQuote],
    last_room_dates: list,
) -> str:
    return _render_period_quote_card_blocks(
        category_name=category_name,
        period_start=period_start,
        period_end=period_end,
        quotes=quotes,
        last_room_dates=last_room_dates,
        period_label="\U0001f48e \u0421\u0430\u043c\u044b\u0439 \u0432\u044b\u0433\u043e\u0434\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434:",
        pricing_mode="per_night",
    )


def _render_period_quote_card_blocks(
    *,
    category_name: str,
    period_start,
    period_end,
    quotes: list[PeriodQuote],
    last_room_dates: list,
    period_label: str | None = None,
    pricing_mode: str = "total",
) -> str:
    blocks = [f"\U0001f3e1 {category_name}"]

    if period_label:
        blocks.append(
            "\n".join(
                [
                    period_label,
                    f"\U0001f4c5 {format_booking_period(start_date=period_start, end_date_inclusive=period_end, separator=' \u2013 ')}",
                ]
            )
        )
    else:
        blocks.append(
            f"\U0001f4c5 {format_booking_period(start_date=period_start, end_date_inclusive=period_end, separator=' \u2013 ')}"
        )

    if pricing_mode == "per_night":
        tariff_blocks = ["\n".join(_render_tariff_block_per_night(quote)) for quote in _sorted_quotes(quotes)]
    else:
        tariff_blocks = ["\n".join(_render_tariff_block(summary)) for summary in _build_tariff_summaries(quotes)]
    if tariff_blocks:
        blocks.append("\n\n".join(tariff_blocks))

    discount_lines = _render_discount_lines(quotes)
    if discount_lines:
        blocks.append("\n".join(["\u2728 \u041f\u0440\u0438\u043c\u0435\u043d\u0451\u043d\u043d\u044b\u0435 \u0441\u043a\u0438\u0434\u043a\u0438", *discount_lines]))

    if last_room_dates:
        formatted_dates = ", ".join(format_date(value) for value in sorted(set(last_room_dates)))
        blocks.append("\n".join(["\u26a0\ufe0f \u041e\u0441\u0442\u0430\u043b\u0438\u0441\u044c \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 \u0434\u0430\u0442\u044b", formatted_dates]))

    return "\n\n".join(blocks).strip()


def render_period_quote_card_legacy(
    *,
    category_name: str,
    period_start,
    period_end,
    quotes: list[PeriodQuote],
    last_room_dates: list,
) -> str:
    lines = [
        category_name,
        format_booking_period(start_date=period_start, end_date_inclusive=period_end, separator=" - "),
        "",
    ]

    for quote in _sorted_quotes(quotes):
        lines.extend(_render_tariff_block_legacy(quote))
        lines.append("")

    discount_lines = _render_discount_lines_legacy(quotes)
    if discount_lines:
        lines.append("\u041f\u0440\u0438\u043c\u0435\u043d\u0451\u043d\u043d\u044b\u0435 \u0441\u043a\u0438\u0434\u043a\u0438:")
        lines.extend(discount_lines)
        lines.append("")

    if last_room_dates:
        formatted_dates = ", ".join(format_date(value) for value in sorted(set(last_room_dates)))
        lines.append(f"\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 \u043d\u043e\u043c\u0435\u0440\u0430 \u043d\u0430 \u0434\u0430\u0442\u044b: {formatted_dates}")

    return "\n".join(line for line in lines if line is not None).strip()


def render_period_quote_offer_text(*, offer_title: str | None, offer_text: str) -> str:
    title = offer_title or "\u0421\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435"
    return f"\u0421\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435: \u00ab{title}\u00bb\n\n{offer_text}".strip()


def format_date(value) -> str:
    return format_ui_date(value)


def _render_tariff_block(summary: TariffQuoteSummary) -> list[str]:
    benefit_minor = summary.total_old_minor - summary.total_new_minor
    lines = [f"\U0001f37d {tariff_label(summary.tariff)}"]
    lines.extend(
        [
            f"\u0426\u0435\u043d\u0430 \u0440\u044b\u043d\u043a\u0430: {format_minor_amount(summary.total_old_minor)} \u20bd \u0437\u0430 \u043f\u0435\u0440\u0438\u043e\u0434",
            f"\u0412\u0430\u0448\u0430 \u0446\u0435\u043d\u0430: {format_minor_amount(summary.total_new_minor)} \u20bd \u0437\u0430 \u043f\u0435\u0440\u0438\u043e\u0434",
            f"\u0412\u044b\u0433\u043e\u0434\u0430: {format_minor_amount(benefit_minor)} \u20bd \u0437\u0430 \u043f\u0435\u0440\u0438\u043e\u0434",
        ]
    )
    return lines


def _render_tariff_block_per_night(quote: PeriodQuote) -> list[str]:
    old_per_night = _minor_per_night(quote.total_old_minor, quote.nights)
    new_per_night = _minor_per_night(quote.total_new_minor, quote.nights)
    benefit = old_per_night - new_per_night

    lines = [f"\U0001f37d {tariff_label(quote.tariff)}"]
    if quote.applied_from != quote.from_date or quote.applied_to != quote.to_date:
        lines.append(
            f"\u041f\u0435\u0440\u0438\u043e\u0434 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0442\u0430\u0440\u0438\u0444\u0430: "
            f"{format_booking_period(start_date=quote.applied_from, end_date_inclusive=quote.applied_to, separator=' \u2013 ')}"
        )
    lines.extend(
        [
            f"\u0426\u0435\u043d\u0430 \u0440\u044b\u043d\u043a\u0430: {format_money(old_per_night)} \u20bd/\u0441\u0443\u0442\u043a\u0438",
            f"\u0412\u0430\u0448\u0430 \u0446\u0435\u043d\u0430: {format_money(new_per_night)} \u20bd/\u0441\u0443\u0442\u043a\u0438",
            f"\u0412\u044b\u0433\u043e\u0434\u0430: {format_money(benefit)} \u20bd/\u0441\u0443\u0442\u043a\u0438",
        ]
    )
    return lines


def _render_tariff_block_legacy(quote: PeriodQuote) -> list[str]:
    old_per_night = _minor_per_night(quote.total_old_minor, quote.nights)
    new_per_night = _minor_per_night(quote.total_new_minor, quote.nights)
    benefit = old_per_night - new_per_night

    lines = [f"\u0422\u0430\u0440\u0438\u0444: {tariff_label(quote.tariff)}"]
    if quote.applied_from != quote.from_date or quote.applied_to != quote.to_date:
        lines.append(
            f"\u041f\u0435\u0440\u0438\u043e\u0434 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0442\u0430\u0440\u0438\u0444\u0430: "
            f"{format_booking_period(start_date=quote.applied_from, end_date_inclusive=quote.applied_to, separator=' - ')}"
        )
    lines.extend(
        [
            f"\u0426\u0435\u043d\u0430 \u043e\u0442\u043a\u0440\u044b\u0442\u043e\u0433\u043e \u0440\u044b\u043d\u043a\u0430: {format_money_legacy(old_per_night)} \u20bd/\u0441\u0443\u0442\u043a\u0438",
            f"\u0412\u0430\u0448\u0430 \u0446\u0435\u043d\u0430: {format_money_legacy(new_per_night)} \u20bd/\u0441\u0443\u0442\u043a\u0438",
            f"\u0412\u0430\u0448\u0430 \u0432\u044b\u0433\u043e\u0434\u0430: {format_money_legacy(benefit)} \u20bd/\u0441\u0443\u0442\u043a\u0438",
        ]
    )
    return lines


def _render_discount_lines(quotes: Iterable[PeriodQuote]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for offer_title, offer_repr, applied_from, applied_to in _merge_offer_periods(quotes):
        offer_name = f"\u00ab{offer_title}\u00bb" if offer_title else "\u0421\u043f\u0435\u0446\u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435"
        period_suffix = ""
        if applied_from and applied_to:
            period_suffix = (
                " , \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u0441\u043f\u0435\u0446\u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044f "
                f"{format_booking_period(start_date=applied_from, end_date_inclusive=applied_to, separator=' \u2013 ')}"
            )
        label = f"\u2022 {offer_name} \u2014 {offer_repr}{period_suffix}"
        if label not in seen:
            lines.append(label)
            seen.add(label)

    for quote in quotes:
        if quote.offer_repr:
            continue
        if quote.bank_status and quote.bank_percent is not None:
            label = f"\u2022 {_format_bank_discount_name(quote.bank_status)} \u2014 {_format_percent_text(quote.bank_percent)}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
        elif quote.loyalty_status and quote.loyalty_percent is not None:
            status = quote.loyalty_status.capitalize()
            label = f"\u2022 {status} \u2014 {_format_percent_text(quote.loyalty_percent)}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
    return lines


def _render_discount_lines_legacy(quotes: Iterable[PeriodQuote]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for quote in quotes:
        if quote.offer_title or quote.offer_repr:
            label = f"\u2022 \u0421\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0435 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u0435: \u00ab{quote.offer_title or '\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f'}\u00bb"
            if quote.offer_repr:
                label += f" - {quote.offer_repr}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
        if quote.bank_status and quote.bank_percent:
            label = f"\u2022 \u0421\u0442\u0430\u0442\u0443\u0441 \u0432 \u0421\u0431\u0435\u0440\u0435: {quote.bank_status} - {quote.bank_percent}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
        elif quote.loyalty_status and quote.loyalty_percent:
            status = quote.loyalty_status.capitalize()
            label = f"\u2022 \u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u043b\u043e\u044f\u043b\u044c\u043d\u043e\u0441\u0442\u0438: {status} - {quote.loyalty_percent}"
            if label not in seen:
                lines.append(label)
                seen.add(label)
    return lines


def _minor_per_night(total_minor: int, nights: int) -> Decimal:
    if nights <= 0:
        return Decimal("0")
    return (Decimal(total_minor) / Decimal("100") / Decimal(nights)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_money(amount: Decimal) -> str:
    minor = int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return format_price_minor(minor)


def format_minor_amount(amount_minor: int) -> str:
    return format_price_minor(amount_minor)


def format_money_legacy(amount: Decimal) -> str:
    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized == normalized.to_integral():
        return f"{int(normalized):,}".replace(",", " ")
    return f"{normalized:,.2f}".replace(",", " ")


def tariff_label(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "breakfast":
        return "\u0422\u043e\u043b\u044c\u043a\u043e \u0437\u0430\u0432\u0442\u0440\u0430\u043a\u0438"
    if normalized == "fullpansion":
        return "\u041f\u043e\u043b\u043d\u044b\u0439 \u043f\u0430\u043d\u0441\u0438\u043e\u043d"
    return value


def _sorted_quotes(quotes: list[PeriodQuote]) -> list[PeriodQuote]:
    order = {"breakfast": 0, "fullpansion": 1}
    return sorted(quotes, key=lambda item: (order.get(item.tariff.strip().lower(), 99), item.applied_from, item.applied_to))


def _merge_offer_periods(quotes: Iterable[PeriodQuote]) -> list[tuple[str | None, str, object, object]]:
    offer_quotes = [
        quote
        for quote in quotes
        if quote.offer_repr
    ]
    if not offer_quotes:
        return []

    ordered = sorted(
        offer_quotes,
        key=lambda item: (
            item.offer_title or "",
            item.offer_repr or "",
            item.applied_from,
            item.applied_to,
        ),
    )

    merged: list[tuple[str | None, str, object, object]] = []
    current = ordered[0]
    current_title = current.offer_title
    current_repr = current.offer_repr or ""
    current_start = current.applied_from
    current_end = current.applied_to

    for quote in ordered[1:]:
        if (
            quote.offer_title == current_title
            and (quote.offer_repr or "") == current_repr
            and quote.applied_from <= current_end + timedelta(days=1)
        ):
            if quote.applied_to > current_end:
                current_end = quote.applied_to
            continue

        merged.append((current_title, current_repr, current_start, current_end))
        current_title = quote.offer_title
        current_repr = quote.offer_repr or ""
        current_start = quote.applied_from
        current_end = quote.applied_to

    merged.append((current_title, current_repr, current_start, current_end))
    return merged


def _build_tariff_summaries(quotes: list[PeriodQuote]) -> list[TariffQuoteSummary]:
    grouped: dict[str, TariffQuoteSummary] = {}
    order = {"breakfast": 0, "fullpansion": 1}

    for quote in quotes:
        key = quote.tariff.strip().lower()
        current = grouped.get(key)
        if current is None:
            grouped[key] = TariffQuoteSummary(
                tariff=quote.tariff,
                total_old_minor=quote.total_old_minor,
                total_new_minor=quote.total_new_minor,
            )
            continue
        grouped[key] = TariffQuoteSummary(
            tariff=current.tariff,
            total_old_minor=current.total_old_minor + quote.total_old_minor,
            total_new_minor=current.total_new_minor + quote.total_new_minor,
        )

    return sorted(grouped.values(), key=lambda item: (order.get(item.tariff.strip().lower(), 99), item.tariff))


def _format_percent_text(value: str) -> str:
    raw = value.strip()
    if raw.endswith("%"):
        return raw
    try:
        decimal_value = Decimal(raw)
    except Exception:
        return raw
    if decimal_value <= Decimal("1"):
        decimal_value *= Decimal("100")
    normalized = decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if normalized == normalized.to_integral():
        return f"{int(normalized)}%"
    return f"{normalized.normalize()}%".replace(".", ",")


def _format_bank_discount_name(bank_status: str) -> str:
    labels = {
        "SBER_PREMIER": "\u0421\u0431\u0435\u0440\u041f\u0440\u0435\u043c\u044c\u0435\u0440",
        "SBER_FIRST": "\u0421\u0431\u0435\u0440\u041f\u0435\u0440\u0432\u044b\u0439",
        "SBER_PRIVATE": "\u0421\u0431\u0435\u0440\u041f\u0440\u0430\u0439\u0432\u0430\u0442",
    }
    return labels.get(bank_status, bank_status)
