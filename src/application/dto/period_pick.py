from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class PeriodPickDTO:
    category_name: str
    group_id: str
    tariff_code: str
    start_date: date
    end_date_inclusive: date
    nights: int
    old_price_per_night: Money
    new_price_per_night: Money
    offer_title: Optional[str]
    offer_repr: Optional[str]
    offer_min_nights: Optional[int]
    applied_loyalty_status: Optional[str]
    applied_loyalty_percent: Optional[str]
    applied_bank_status: Optional[BankStatus] = None
    applied_bank_percent: Optional[Decimal] = None
