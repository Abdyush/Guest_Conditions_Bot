from __future__ import annotations

from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote
from src.presentation.telegram.presenters.booking_period import format_booking_period
from src.presentation.telegram.presenters.period_quotes_presenter import (
    render_period_quote_card,
    render_period_quote_offer_text,
)


def render_best_groups_prompt() -> str:
    return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0433\u0440\u0443\u043f\u043f\u0443 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0439, \u0447\u0442\u043e\u0431\u044b \u043f\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0441\u0430\u043c\u044b\u0439 \u0432\u044b\u0433\u043e\u0434\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434."


def render_best_categories_prompt() -> str:
    return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e."


def render_best_period_flow_hint() -> str:
    return (
        "\u0421\u0435\u0439\u0447\u0430\u0441 \u043e\u0442\u043a\u0440\u044b\u0442 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439 "
        "\u00ab\u0421\u0430\u043c\u044b\u0439 \u0432\u044b\u0433\u043e\u0434\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434\u00bb. "
        "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043a\u043d\u043e\u043f\u043a\u0438 \u044d\u0442\u043e\u0433\u043e \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u044f "
        "\u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u00ab\u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e\u00bb."
    )


def render_best_period_empty(*, category_name: str) -> str:
    return f"\u0414\u043b\u044f \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438 \u00ab{category_name}\u00bb \u0441\u0435\u0439\u0447\u0430\u0441 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u0439 \u0441\u0430\u043c\u044b\u0439 \u0432\u044b\u0433\u043e\u0434\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434."


def render_best_period_card(
    *,
    category_name: str,
    best_pick: PeriodPickDTO,
    quotes: list[PeriodQuote],
    last_room_dates: list,
) -> str:
    header = (
        f"{category_name}\n"
        f"\u0421\u0430\u043c\u044b\u0439 \u0432\u044b\u0433\u043e\u0434\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434: "
        f"{format_booking_period(start_date=best_pick.start_date, end_date_inclusive=best_pick.end_date_inclusive, separator=' - ')}\n\n"
        "\u0412\u043e\u0442 \u0441\u0430\u043c\u044b\u0439 \u0432\u044b\u0433\u043e\u0434\u043d\u044b\u0439 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438:\n"
    )
    body = render_period_quote_card(
        category_name=category_name,
        period_start=best_pick.start_date,
        period_end=best_pick.end_date_inclusive,
        quotes=quotes,
        last_room_dates=last_room_dates,
    )
    return f"{header}\n{body}".strip()


def render_best_offer_text(*, offer_title: str | None, offer_text: str) -> str:
    return render_period_quote_offer_text(offer_title=offer_title, offer_text=offer_text)
