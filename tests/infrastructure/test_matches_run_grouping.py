from datetime import date, datetime
from decimal import Decimal

from src.application.dto.matched_date_record import MatchedDateRecord
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository


def _row(day: date, *, tariff: str = "breakfast", new_price_minor: int = 9000) -> MatchedDateRecord:
    availability_start = date(2026, 2, 24)
    availability_end_exclusive = date(2026, 3, 11)
    return MatchedDateRecord(
        guest_id="g1",
        date=day,
        category_name="Deluxe",
        group_id="DELUXE",
        tariff=tariff,
        old_price_minor=10000,
        new_price_minor=new_price_minor,
        offer_id=None,
        offer_title=None,
        offer_repr=None,
        offer_min_nights=None,
        loyalty_status="gold",
        loyalty_percent=Decimal("0.10"),
        bank_status=None,
        bank_percent=None,
        availability_start=availability_start,
        availability_end=availability_end_exclusive,
        computed_at=datetime(2026, 2, 1, 12, 0, 0),
    )


def test_aggregate_rows_groups_only_consecutive_days_with_same_key():
    rows = [
        _row(date(2026, 2, 24)),
        _row(date(2026, 2, 25)),
        _row(date(2026, 2, 26)),
        _row(date(2026, 2, 28)),  # break in continuity -> new period
        _row(date(2026, 2, 24), tariff="fullpansion"),  # different tariff -> separate period
        _row(date(2026, 2, 25), new_price_minor=9100),  # different price -> separate period
    ]

    grouped = PostgresMatchesRunRepository._aggregate_rows(rows)

    assert len(grouped) == 4

    breakfast_first = [x for x in grouped if x.tariff == "breakfast" and x.new_price_minor == 9000][0]
    assert breakfast_first.availability_start == date(2026, 2, 24)
    assert breakfast_first.availability_end == date(2026, 3, 11)
    assert breakfast_first.date == date(2026, 2, 24)
    assert breakfast_first.period_end == date(2026, 2, 26)

    breakfast_second = [x for x in grouped if x.tariff == "breakfast" and x.new_price_minor == 9000 and x.date == date(2026, 2, 28)][0]
    assert breakfast_second.date == date(2026, 2, 28)
    assert breakfast_second.period_end == date(2026, 2, 28)
