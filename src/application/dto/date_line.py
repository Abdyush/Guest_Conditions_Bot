from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.date_range import DateRange
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class DateLineDTO:
    date: date
    category_name: str
    group_id: str
    availability_period: DateRange
    tariff_code: str
    old_price: Money
    new_price: Money
    offer_title: Optional[str]
    offer_repr: Optional[str]
    offer_min_nights: Optional[int]
    applied_bank_status: Optional[BankStatus]
    applied_bank_percent: Optional[Decimal]
    applied_loyalty_status: Optional[str]
    applied_loyalty_percent: Optional[str]
    offer_id: Optional[str]
