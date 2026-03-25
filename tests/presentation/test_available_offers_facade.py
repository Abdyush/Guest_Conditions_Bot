from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from src.application.dto.matched_date_record import MatchedDateRecord
from src.presentation.telegram.services.use_cases_adapter import TelegramAvailableOffersFacade


class _DesiredMatchesRepo:
    def __init__(self, run_id: str, rows: list[MatchedDateRecord]):
        self._run_id = run_id
        self._rows = rows

    def get_latest_run_id(self) -> str | None:
        return self._run_id

    def get_run_rows(self, run_id: str) -> list[MatchedDateRecord]:
        assert run_id == self._run_id
        return list(self._rows)


def _row(*, guest_id: str, category_name: str, group_id: str, price_minor: int) -> MatchedDateRecord:
    return MatchedDateRecord(
        guest_id=guest_id,
        date=date(2026, 2, 10),
        category_name=category_name,
        group_id=group_id,
        tariff="breakfast",
        old_price_minor=10000,
        new_price_minor=price_minor,
        offer_id=None,
        offer_title=None,
        offer_repr=None,
        offer_min_nights=None,
        loyalty_status="gold",
        loyalty_percent=Decimal("0.10"),
        bank_status=None,
        bank_percent=None,
        availability_start=date(2026, 2, 10),
        availability_end=date(2026, 2, 11),
        computed_at=datetime(2026, 2, 1, 12, 0, 0),
        period_end=date(2026, 2, 10),
    )


def test_available_offers_facade_reads_live_desired_matches_snapshot():
    rows = [
        _row(guest_id="g1", category_name="Deluxe", group_id="DELUXE", price_minor=9000),
        _row(guest_id="g1", category_name="Suite", group_id="SUITE", price_minor=11000),
        _row(guest_id="g2", category_name="Villa", group_id="VILLA", price_minor=15000),
    ]
    ctx = SimpleNamespace(
        desired_matches_run_repo=_DesiredMatchesRepo("run_live", rows),
    )

    facade = TelegramAvailableOffersFacade(ctx=ctx)

    assert facade.get_available_categories(guest_id="g1") == ["Deluxe", "Suite"]
    run_id, category_rows = facade.get_category_matches(guest_id="g1", category_name="Deluxe")

    assert run_id == "run_live"
    assert category_rows == [rows[0]]
