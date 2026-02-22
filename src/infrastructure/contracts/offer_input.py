from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Optional


DiscountType = Literal["PERCENT_OFF", "PAY_X_GET_Y"]


@dataclass(frozen=True, slots=True)
class DateRangeInput:
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class OfferInput:
    offer_id: str
    title: str
    loyalty_compatible: bool
    min_nights: int

    booking_period: Optional[DateRangeInput]
    stay_periods: list[DateRangeInput]

    discount_type: DiscountType
    allowed_groups: Optional[list[str]] = None
    allowed_categories: Optional[list[str]] = None
    percent: Optional[Decimal] = None
    x: Optional[int] = None
    y: Optional[int] = None

    raw_text: Optional[str] = None
    raw_formula: Optional[str] = None
