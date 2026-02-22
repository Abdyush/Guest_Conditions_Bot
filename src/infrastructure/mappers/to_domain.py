from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from src.domain.entities.offer import Offer
from src.domain.entities.rate import DailyRate
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import PayXGetY, PercentOff
from src.domain.value_objects.money import Money

from src.infrastructure.contracts.daily_rate_input import DailyRateInput
from src.infrastructure.contracts.offer_input import OfferInput, DateRangeInput


class InputValidationError(ValueError):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise InputValidationError(msg)


def _to_date_range(dr: DateRangeInput) -> DateRange:
    _require(isinstance(dr.start, date), "DateRangeInput.start must be date")
    _require(isinstance(dr.end, date), "DateRangeInput.end must be date")
    _require(dr.end > dr.start, "DateRangeInput must have end > start (end is checkout date)")
    return DateRange(dr.start, dr.end)


def map_daily_rates(inputs: Iterable[DailyRateInput]) -> list[DailyRate]:
    out: list[DailyRate] = []
    for i in inputs:
        _require(i.currency == "RUB", "Only RUB supported right now")
        _require(isinstance(i.date, date), "DailyRateInput.date must be date")
        category_name = i.category_name if i.category_name else i.category_id
        _require(bool(category_name), "DailyRateInput.category_name is required")
        group_id = i.group_id if i.group_id else category_name
        _require(bool(group_id), "DailyRateInput.group_id is required")
        _require(bool(i.tariff_code), "DailyRateInput.tariff_code is required")
        _require(isinstance(i.adults_count, int) and i.adults_count > 0, "adults_count must be int > 0")
        _require(isinstance(i.amount_minor, int) and i.amount_minor >= 0, "amount_minor must be int >= 0")

        price = Money.from_minor(i.amount_minor, currency=i.currency)

        out.append(
            DailyRate(
                date=i.date,
                category_id=category_name,
                group_id=group_id,
                tariff_code=i.tariff_code,
                adults_count=i.adults_count,
                price=price,
                is_available=True,
                is_last_room=bool(i.is_last_room),
            )
        )
    return out


def map_offers(inputs: Iterable[OfferInput]) -> list[Offer]:
    out: list[Offer] = []
    for o in inputs:
        _require(bool(o.offer_id), "offer_id is required")
        _require(bool(o.title), "title is required")
        _require(isinstance(o.min_nights, int) and o.min_nights > 0, "min_nights must be > 0")
        _require(o.stay_periods and len(o.stay_periods) >= 1, "stay_periods must be non-empty")

        booking_period = _to_date_range(o.booking_period) if o.booking_period else None
        stay_periods = [_to_date_range(x) for x in o.stay_periods]

        allowed_groups = None
        if o.allowed_groups is not None:
            _require(isinstance(o.allowed_groups, list), "allowed_groups must be list[str] or None")
            _require(all(isinstance(x, str) and x.strip() for x in o.allowed_groups), "allowed_groups must contain non-empty strings")
            allowed_groups = set(o.allowed_groups)

        allowed_categories = None
        if o.allowed_categories is not None:
            _require(isinstance(o.allowed_categories, list), "allowed_categories must be list[str] or None")
            _require(all(isinstance(x, str) and x.strip() for x in o.allowed_categories), "allowed_categories must contain non-empty strings")
            allowed_categories = set(o.allowed_categories)

        if o.discount_type == "PERCENT_OFF":
            _require(o.percent is not None, "percent is required for PERCENT_OFF")
            _require(Decimal("0") < o.percent < Decimal("1"), "percent must be in (0,1), e.g. 0.30")
            discount = PercentOff(o.percent)
        elif o.discount_type == "PAY_X_GET_Y":
            _require(o.x is not None and o.y is not None, "x and y are required for PAY_X_GET_Y")
            _require(isinstance(o.x, int) and isinstance(o.y, int), "x,y must be ints")
            _require(0 < o.x < o.y, "require 0 < x < y (e.g. 3 < 4)")
            discount = PayXGetY(o.x, o.y)
        else:
            raise InputValidationError(f"Unknown discount_type: {o.discount_type}")

        out.append(
            Offer(
                id=o.offer_id,
                title=o.title,
                description=o.raw_text or "",
                discount=discount,
                stay_periods=stay_periods,
                booking_period=booking_period,
                min_nights=o.min_nights,
                allowed_groups=allowed_groups,
                allowed_categories=allowed_categories,
                loyalty_compatible=bool(o.loyalty_compatible),
            )
        )

    return out
