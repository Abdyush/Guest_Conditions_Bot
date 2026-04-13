from __future__ import annotations

from datetime import date

from src.application.dto.period_quote import PeriodQuote
from src.presentation.telegram.presenters.period_quotes_presenter import render_period_quote_card


def test_render_period_quote_card_shows_offer_and_loyalty_when_both_applied() -> None:
    quote = PeriodQuote(
        category_name="Семейная Винная Вилла",
        group_id="VILLA",
        tariff="breakfast",
        from_date=date(2026, 4, 16),
        to_date=date(2026, 4, 23),
        applied_from=date(2026, 4, 16),
        applied_to=date(2026, 4, 23),
        nights=8,
        total_old_minor=1_908_200_00,
        total_new_minor=1_450_232_00,
        offer_id="offer-1",
        offer_title="Раннее бронирование 2026",
        offer_repr="20%",
        loyalty_status="gold",
        loyalty_percent="0.10",
        bank_status=None,
        bank_percent=None,
    )

    rendered = render_period_quote_card(
        category_name=quote.category_name,
        period_start=quote.from_date,
        period_end=quote.to_date,
        quotes=[quote],
        last_room_dates=[],
    )

    assert "«Раннее бронирование 2026» — 20%" in rendered
    assert "Gold — 10%" in rendered
