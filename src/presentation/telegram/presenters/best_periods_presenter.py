from __future__ import annotations

from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote
from src.presentation.telegram.presenters.period_quotes_presenter import (
    format_date,
    render_period_quote_card,
    render_period_quote_offer_text,
)


def render_best_groups_prompt() -> str:
    return "Выберите группу категорий, чтобы посмотреть самый выгодный период."


def render_best_categories_prompt() -> str:
    return "Выберите категорию."


def render_best_period_flow_hint() -> str:
    return "Сейчас открыт сценарий «Самый выгодный период». Используйте кнопки этого сценария и кнопку «Главное меню»."


def render_best_period_empty(*, category_name: str) -> str:
    return f"Для категории «{category_name}» сейчас не найден подходящий самый выгодный период."


def render_best_period_card(
    *,
    category_name: str,
    best_pick: PeriodPickDTO,
    quotes: list[PeriodQuote],
    last_room_dates: list,
) -> str:
    header = (
        f"{category_name}\n"
        f"Самый выгодный период: {format_date(best_pick.start_date)} - {format_date(best_pick.end_date_inclusive)}\n\n"
        "Вот самый выгодный доступный период для этой категории:\n"
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
