from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.discount import Discount


class OfferError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Offer:
    id: str
    title: str
    description: str
    discount: Discount
    stay_periods: Sequence[DateRange]
    booking_period: Optional[DateRange] = None
    min_nights: Optional[int] = None
    allowed_groups: Optional[set[str]] = None
    allowed_categories: Optional[set[str]] = None
    tariffs: Optional[set[str]] = None
    loyalty_compatible: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise OfferError("id must be non-empty str")
        if not isinstance(self.title, str) or not self.title.strip():
            raise OfferError("title must be non-empty str")
        if not isinstance(self.description, str):
            raise OfferError("description must be str")
        if not isinstance(self.discount, Discount):
            raise OfferError("discount must be Discount")

        if not self.stay_periods:
            raise OfferError("stay_periods must not be empty")
        for period in self.stay_periods:
            if not isinstance(period, DateRange):
                raise OfferError("stay_periods must contain DateRange")

        if self.booking_period is not None and not isinstance(self.booking_period, DateRange):
            raise OfferError("booking_period must be DateRange or None")

        if self.min_nights is not None and (not isinstance(self.min_nights, int) or self.min_nights <= 0):
            raise OfferError("min_nights must be int > 0 if provided")

        if self.allowed_groups is not None:
            invalid = any((not isinstance(x, str) or not x.strip()) for x in self.allowed_groups)
            if not isinstance(self.allowed_groups, set) or invalid:
                raise OfferError("allowed_groups must be set[str] with non-empty strings")

        if self.allowed_categories is not None:
            invalid = any((not isinstance(x, str) or not x.strip()) for x in self.allowed_categories)
            if not isinstance(self.allowed_categories, set) or invalid:
                raise OfferError("allowed_categories must be set[str] with non-empty strings")

        if self.tariffs is not None:
            invalid = any((not isinstance(x, str) or not x.strip()) for x in self.tariffs)
            if not isinstance(self.tariffs, set) or invalid:
                raise OfferError("tariffs must be set[str] with non-empty strings")

        if not isinstance(self.loyalty_compatible, bool):
            raise OfferError("loyalty_compatible must be bool")

    def is_bookable(self, booking_date: date) -> bool:
        if self.booking_period is None:
            return True
        return self.booking_period.contains(booking_date)

    def is_eligible_by_period_length(self, nights: int) -> bool:
        if self.min_nights is None:
            return True
        return nights >= self.min_nights

    def is_applicable(
        self,
        stay_range: DateRange,
        *,
        booking_date: date,
        category_id: str,
        group_id: str,
        tariff_code: str,
    ) -> bool:
        has_limits = (self.allowed_groups is not None) or (self.allowed_categories is not None)
        if has_limits:
            ok = False
            if self.allowed_groups is not None and group_id in self.allowed_groups:
                ok = True
            if self.allowed_categories is not None and category_id in self.allowed_categories:
                ok = True
            if not ok:
                return False

        if not self.is_bookable(booking_date):
            return False

        if self.tariffs is not None and tariff_code not in self.tariffs:
            return False

        for period in self.stay_periods:
            if period.start <= stay_range.start and stay_range.end <= period.end:
                return True

        return False
