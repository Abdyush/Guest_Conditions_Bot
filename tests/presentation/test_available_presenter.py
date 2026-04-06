from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from src.application.dto.matched_date_record import MatchedDateRecord
from src.presentation.telegram.presenters.available_presenter import build_available_periods


def _row(*, stay_date: date, tariff: str, new_price_minor: int, old_price_minor: int = 10000) -> MatchedDateRecord:
    return MatchedDateRecord(
        guest_id="g1",
        date=stay_date,
        category_name="Deluxe",
        group_id="DELUXE",
        tariff=tariff,
        old_price_minor=old_price_minor,
        new_price_minor=new_price_minor,
        offer_id=None,
        offer_title=None,
        offer_repr=None,
        offer_min_nights=None,
        loyalty_status="gold",
        loyalty_percent=Decimal("0.10"),
        bank_status=None,
        bank_percent=None,
        availability_start=stay_date,
        availability_end=stay_date,
        computed_at=datetime(2026, 4, 6, 12, 0, 0),
        period_end=stay_date,
    )


def test_available_period_exposes_button_price_minor_alias() -> None:
    periods = build_available_periods(
        rows=[
            _row(stay_date=date(2026, 4, 10), tariff="breakfast", new_price_minor=41_900_00),
            _row(stay_date=date(2026, 4, 10), tariff="fullpansion", new_price_minor=47_800_00),
        ]
    )

    assert len(periods) == 1
    assert periods[0].min_new_price_minor == 41_900_00
    assert periods[0].button_price_minor == 41_900_00
