from datetime import date

import pytest

from src.application.dto.get_period_quotes_query import GetPeriodQuotesQuery


def d(y, m, day):
    return date(y, m, day)


def test_query_accepts_valid_input():
    q = GetPeriodQuotesQuery(
        guest_id="G1",
        period_start=d(2026, 2, 25),
        period_end=d(2026, 3, 5),
        group_ids={"DELUXE"},
    )
    assert q.guest_id == "G1"


def test_query_rejects_invalid_period():
    with pytest.raises(ValueError):
        GetPeriodQuotesQuery(
            guest_id="G1",
            period_start=d(2026, 3, 6),
            period_end=d(2026, 3, 5),
        )
