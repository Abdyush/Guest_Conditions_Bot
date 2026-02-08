from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class LoyaltyError(ValueError):
    pass


class LoyaltyStatus(str, Enum):
    DIAMOND = "diamond"
    GOLD = "gold"
    PLATINUM = "platinum"
    BRONZE = "bronze"
    SILVER = "silver"
    WHITE = "white"


@dataclass(frozen=True, slots=True)
class LoyaltyPolicy:
    discounts: dict[LoyaltyStatus, Decimal]

    def percent_for(self, status: LoyaltyStatus) -> Decimal:
        if status not in self.discounts:
            raise LoyaltyError(f"No discount for {status}")
        p = self.discounts[status]
        if p < 0 or p > 1:
            raise LoyaltyError("percent must be between 0 and 1")
        return p