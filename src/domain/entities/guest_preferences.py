from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

from src.domain.services.category_capacity import Occupancy
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyStatus
from src.domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class GuestPreferences:
    desired_price_per_night: Money
    loyalty_status: Optional[LoyaltyStatus] = None
    bank_status: Optional[BankStatus] = None
    allowed_groups: Optional[Set[str]] = None
    # Backward-compatible alias.
    allowed_categories: Optional[Set[str]] = None
    occupancy: Occupancy = Occupancy(adults=1, children_4_13=0, infants=0)
    guest_id: Optional[str] = None
    guest_name: Optional[str] = None
    guest_phone: Optional[str] = None

    @property
    def effective_allowed_groups(self) -> Optional[Set[str]]:
        return self.allowed_groups if self.allowed_groups is not None else self.allowed_categories
