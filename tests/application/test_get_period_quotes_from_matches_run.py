from datetime import date, datetime, timedelta
from decimal import Decimal

from src.application.dto.get_period_quotes_query import GetPeriodQuotesQuery
from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.use_cases.get_period_quotes_from_matches_run import GetPeriodQuotesFromMatchesRun


def d(y, m, day):
    return date(y, m, day)


def _record(day_from: date, day_to: date, *, old_minor: int, new_minor: int) -> MatchedDateRecord:
    return MatchedDateRecord(
        guest_id="G1",
        date=day_from,
        category_name="Deluxe",
        group_id="DELUXE",
        tariff="breakfast",
        old_price_minor=old_minor,
        new_price_minor=new_minor,
        offer_id="WINTER_15",
        offer_title="Winter 15%",
        offer_repr="15%",
        offer_min_nights=2,
        loyalty_status="bronze",
        loyalty_percent=Decimal("0.0700"),
        bank_status=None,
        bank_percent=None,
        availability_start=d(2026, 2, 24),
        availability_end=d(2026, 3, 11),
        computed_at=datetime(2026, 2, 24, 12, 0, 0),
        period_end=day_to,
    )


class FakeMatchesRepo:
    def get_latest_run_id(self) -> str | None:
        return "run_latest"

    def get_run_rows(self, run_id: str) -> list[MatchedDateRecord]:
        _ = run_id
        return [
            _record(d(2026, 2, 24), d(2026, 2, 27), old_minor=7560000, new_minor=5976180),
            _record(d(2026, 2, 28), d(2026, 3, 10), old_minor=7560000, new_minor=7030800),
        ]


def test_period_quotes_sum_across_different_price_periods():
    use_case = GetPeriodQuotesFromMatchesRun(FakeMatchesRepo())
    query = GetPeriodQuotesQuery(
        guest_id="G1",
        period_start=d(2026, 2, 25),
        period_end=d(2026, 3, 5),
        group_ids={"DELUXE"},
        run_id=None,
    )
    run_id, quotes = use_case.execute(query)

    assert run_id == "run_latest"
    assert len(quotes) == 2
    q1, q2 = quotes
    assert q1.applied_from == d(2026, 2, 25)
    assert q1.applied_to == d(2026, 2, 27)
    assert q1.nights == 3
    assert q1.total_old_minor == 7560000 * 3
    assert q1.total_new_minor == 5976180 * 3
    assert q2.applied_from == d(2026, 2, 28)
    assert q2.applied_to == d(2026, 3, 5)
    assert q2.nights == 6
    assert q2.total_old_minor == 7560000 * 6
    assert q2.total_new_minor == 7030800 * 6
