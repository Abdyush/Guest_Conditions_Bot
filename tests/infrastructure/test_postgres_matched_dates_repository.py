import os
from datetime import date, datetime, timedelta
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


def _record(
    *,
    guest_id: str,
    day: date,
    period_end: date | None = None,
    new_price_minor: int = 9000,
    offer_id: str | None = None,
) -> MatchedDateRecord:
    end = period_end or day
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
        availability_end=end + timedelta(days=1),
        computed_at=datetime(2026, 2, 1, 12, 0, 0),
        period_end=end,
    )


def _set_notified_at(repo: PostgresNotificationsRepository, *, notified_at: datetime) -> None:
    with repo._engine.begin() as conn:  # type: ignore[attr-defined]
        conn.execute(text("UPDATE notifications SET notified_at = :notified_at"), {"notified_at": notified_at})


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
        conn.execute(text("TRUNCATE TABLE notifications"))
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

    notifications_repo.mark_sent([sent], run_id="run_old")

    new_rows = notifications_repo.filter_new(
        [candidate_same, candidate_changed_price],
        as_of_date=date(2026, 2, 10),
        cooldown_days=7,
    )

    assert new_rows == []


def test_notifications_ignore_same_price_period_extension(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), period_end=date(2026, 2, 12), new_price_minor=9000)
    candidate_extended = _record(guest_id="g1", day=date(2026, 2, 10), period_end=date(2026, 2, 13), new_price_minor=9000)

    notifications_repo.mark_sent([sent], run_id="run_old")

    new_rows = notifications_repo.filter_new([candidate_extended], as_of_date=date(2026, 2, 10), cooldown_days=7)

    assert new_rows == []


def test_notifications_ignore_worse_price(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000)
    candidate_worse = _record(guest_id="g1", day=date(2026, 2, 10), period_end=date(2026, 2, 12), new_price_minor=9300)

    notifications_repo.mark_sent([sent], run_id="run_old")

    new_rows = notifications_repo.filter_new([candidate_worse], as_of_date=date(2026, 2, 10), cooldown_days=7)

    assert new_rows == []


def test_notifications_send_on_price_improvement(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000)
    candidate_better = _record(guest_id="g1", day=date(2026, 2, 10), period_end=date(2026, 2, 13), new_price_minor=8800)

    notifications_repo.mark_sent([sent], run_id="run_old")

    new_rows = notifications_repo.filter_new([candidate_better], as_of_date=date(2026, 2, 10), cooldown_days=7)

    assert new_rows == [candidate_better]


def test_notifications_payload_contains_only_best_price_rows(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000)
    best_row = _record(guest_id="g1", day=date(2026, 2, 11), period_end=date(2026, 2, 12), new_price_minor=8800)
    worse_row = _record(guest_id="g1", day=date(2026, 2, 13), period_end=date(2026, 2, 14), new_price_minor=8950)

    notifications_repo.mark_sent([sent], run_id="run_old")

    new_rows = notifications_repo.filter_new(
        [best_row, worse_row],
        as_of_date=date(2026, 2, 10),
        cooldown_days=7,
    )

    assert new_rows == [best_row]


def test_notifications_payload_keeps_all_equal_best_rows(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000)
    best_row_1 = _record(guest_id="g1", day=date(2026, 2, 11), period_end=date(2026, 2, 12), new_price_minor=8800)
    best_row_2 = _record(guest_id="g1", day=date(2026, 2, 13), period_end=date(2026, 2, 14), new_price_minor=8800)
    worse_row = _record(guest_id="g1", day=date(2026, 2, 15), period_end=date(2026, 2, 16), new_price_minor=8950)

    notifications_repo.mark_sent([sent], run_id="run_old")

    new_rows = notifications_repo.filter_new(
        [best_row_1, best_row_2, worse_row],
        as_of_date=date(2026, 2, 10),
        cooldown_days=7,
    )

    assert new_rows == [best_row_1, best_row_2]


def test_notifications_send_reminder_after_cooldown(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000)
    candidate_same = _record(guest_id="g1", day=date(2026, 2, 11), period_end=date(2026, 2, 13), new_price_minor=9000)

    notifications_repo.mark_sent([sent], run_id="run_old")
    _set_notified_at(notifications_repo, notified_at=datetime(2026, 2, 1, 9, 0, 0))

    new_rows = notifications_repo.filter_new([candidate_same], as_of_date=date(2026, 2, 10), cooldown_days=7)

    assert new_rows == [candidate_same]


def test_notifications_do_not_send_reminder_before_cooldown(notifications_repo: PostgresNotificationsRepository):
    sent = _record(guest_id="g1", day=date(2026, 2, 10), new_price_minor=9000)
    candidate_same = _record(guest_id="g1", day=date(2026, 2, 11), period_end=date(2026, 2, 13), new_price_minor=9000)

    notifications_repo.mark_sent([sent], run_id="run_old")
    _set_notified_at(notifications_repo, notified_at=datetime(2026, 2, 7, 9, 0, 0))

    new_rows = notifications_repo.filter_new([candidate_same], as_of_date=date(2026, 2, 10), cooldown_days=7)

    assert new_rows == []
