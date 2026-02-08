from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

from src.domain.value_objects.loyalty import LoyaltyStatus
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class GuestPreferences:
    desired_price_per_night: Money
    loyalty_status: Optional[LoyaltyStatus] = None
    allowed_categories: Optional[Set[str]] = None  # None => любые