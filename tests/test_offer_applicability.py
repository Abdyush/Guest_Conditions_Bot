from datetime import date
from decimal import Decimal

from src.domain.entities.offer import Offer
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PercentOff


def d(y, m, day):
    return date(y, m, day)


def _offer(**kwargs) -> Offer:
    base = dict(
        id="o",
        title="test",
        description="",
        discount=PercentOff(Decimal("0.10")),
        stay_periods=[DateRange(d(2026, 2, 1), d(2026, 3, 1))],
        booking_period=DateRange(d(2026, 2, 1), d(2026, 2, 28)),
        min_nights=1,
        loyalty_compatible=True,
    )
    base.update(kwargs)
    return Offer(**base)


def test_offer_restricted_by_group_applies_to_any_category_in_group():
    offer = _offer(allowed_groups={"DELUXE"})

    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Deluxe Mountain View",
        group_id="DELUXE",
        tariff_code="breakfast",
    ) is True
    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Royal Suite",
        group_id="ROYAL_SUITE",
        tariff_code="breakfast",
    ) is False


def test_offer_restricted_by_category_applies_only_to_exact_category():
    offer = _offer(allowed_categories={"Exact Category"})

    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Exact Category",
        group_id="ANY_GROUP",
        tariff_code="breakfast",
    ) is True
    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Other Category",
        group_id="ANY_GROUP",
        tariff_code="breakfast",
    ) is False


def test_offer_with_groups_and_categories_uses_or_logic():
    offer = _offer(allowed_groups={"VILLA"}, allowed_categories={"Exact Category"})

    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Other Villa Category",
        group_id="VILLA",
        tariff_code="breakfast",
    ) is True
    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Exact Category",
        group_id="NOT_VILLA",
        tariff_code="breakfast",
    ) is True
    assert offer.is_applicable(
        DateRange(d(2026, 2, 10), d(2026, 2, 11)),
        booking_date=d(2026, 2, 10),
        category_id="Other Category",
        group_id="NOT_VILLA",
        tariff_code="breakfast",
    ) is False


def test_is_eligible_by_period_length():
    offer = _offer(min_nights=3)
    assert offer.is_eligible_by_period_length(2) is False
    assert offer.is_eligible_by_period_length(3) is True
