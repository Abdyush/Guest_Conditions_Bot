from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class BankPolicyError(ValueError):
    pass


class BankStatus(str, Enum):
    SBER_PREMIER = "SBER_PREMIER"
    SBER_FIRST = "SBER_FIRST"
    SBER_PRIVATE = "SBER_PRIVATE"


@dataclass(frozen=True, slots=True)
class BankDiscount:
    open_percent: Decimal
    after_offer_percent: Decimal


class BankPolicy:
    def __init__(self, discounts: dict[BankStatus, BankDiscount]):
        self._discounts = discounts

    def discount_for(self, status: BankStatus) -> BankDiscount:
        if status not in self._discounts:
            raise BankPolicyError(f"No bank discount for {status}")
        return self._discounts[status]

    @staticmethod
    def default() -> "BankPolicy":
        return BankPolicy(
            {
                BankStatus.SBER_PREMIER: BankDiscount(
                    open_percent=Decimal("0.20"),
                    after_offer_percent=Decimal("0.10"),
                ),
                BankStatus.SBER_FIRST: BankDiscount(
                    open_percent=Decimal("0.25"),
                    after_offer_percent=Decimal("0.15"),
                ),
                BankStatus.SBER_PRIVATE: BankDiscount(
                    open_percent=Decimal("0.30"),
                    after_offer_percent=Decimal("0.15"),
                ),
            }
        )
