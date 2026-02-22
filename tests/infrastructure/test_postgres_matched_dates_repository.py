import os
from datetime import date, datetime
from decimal import Decimal

import pytest

pytest.importorskip("sqlalchemy")

PG_TEST_DATABASE_URL = os.getenv("PG_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not PG_TEST_DATABASE_URL,
    reason="Set PG_TEST_DATABASE_URL to run postgres persistence repository tests",
)

from sqlalchemy import text

from src.application.dto.matched_date_record import MatchedDateRecord
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository
from src.infrastructure.repositories.postgres_notifications_repository import PostgresNotificationsRepository


def _record(*, guest_id: str, day: date, new_price_minor: int = 9000, offer_id: str | None = None) -> MatchedDateRecord:
    return MatchedDateRecord(
        guest_id=guest_id,
        date=day,
        category_name="Deluxe",
        group_id="DELUXE",
        tariff="breakfast",
        old_price_minor=10000,
        new_price_minor=new_price_minor,
        offer_id=offer_id,
        offer_title=None,
        offer_repr=None,
        offer_min_nights=None,
        loyalty_status="gold",
        loyalty_percent=Decimal("0.10"),
        bank_status=None,
        bank_percent=None,
        availability_start=day,
        availability_end=day,
        computed_at=datetime(2026, 2, 1, 12, 0, 0),
    )


@pytest.fixture
def matches_repo() -> PostgresMatchesRunRepository:
    repo = PostgresMatchesRunRepository(PG_TEST_DATABASE_URL)
    with repo._engine.begin() as conn:  # type: ignore[attr-defined]
        conn.execute(text("TRUNCATE TABLE matches_run"))
    return repo


@pytest.fixture
def notifications_repo() -> PostgresNotificationsRepository:
    repo = PostgresNotificationsRepository(PG_TEST_DATABASE_URL)
    with repo._engine.begin() as conn:  # type: ignore[attr-defined]
        conn.execute(text("TRUNCATE TABLE notifications RESTART IDENTITY"))
    return repo


def test_run_replace(matches_repo: PostgresMatchesRunRepository):
    run_id_1 = "run_1"
    run_id_2 = "run_2"
    first_rows = [_record(guest_id="g1", day=date(2026, 2, 10))]
    second_rows = [
        _record(guest_id="g2", day=date(2026, 2, 11), new_price_minor=8500),
        _record(guest_id="g3", day=date(2026, 2, 12), new_price_minor=8300),
    ]

    matches_repo.replace_run(run_id_1, first_rows)
    matches_repo.replace_run(run_id_2, second_rows)

    run_1_rows = matches_repo.get_run_rows(run_id_1)
    run_2_rows = matches_repo.get_run_rows(run_id_2)

    assert run_1_rows == []
    assert len(run_2_rows) == 2
    assert {r.guest_id for r in run_2_rows} == {"g2", "g3"}


def test_notifications_dedup(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000, offer_id="o1")
    candidate_same = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000, offer_id="o1")
    candidate_changed_price = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9100, offer_id="o1")

    notifications_repo.mark_sent([sent], sent_at=datetime(2026, 2, 1, 12, 0, 0))

    new_rows = notifications_repo.filter_new([candidate_same, candidate_changed_price])

    assert new_rows == [candidate_changed_price]
