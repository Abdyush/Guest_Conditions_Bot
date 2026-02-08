from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

TWOPLACES = Decimal("0.01")


class MoneyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise MoneyError("Money.amount must be Decimal")
        if self.currency != "RUB":
            # если позже понадобится — расширишь
            raise MoneyError("Only RUB is supported for now")
        if self.amount.is_nan() or self.amount.is_infinite():
            raise MoneyError("Invalid amount")
        # нормализуем до копеек
        object.__setattr__(self, "amount", self.amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP))

    # --- Constructors ---
    @staticmethod
    def rub(value: Any) -> "Money":
        """
        Создаёт Money из:
        - Decimal
        - int (рубли)
        - str ("123", "123.45", "123,45")
        """
        if isinstance(value, Money):
            return value
        if isinstance(value, Decimal):
            return Money(value)
        if isinstance(value, int):
            return Money(Decimal(value))
        if isinstance(value, str):
            v = value.strip().replace(" ", "").replace(",", ".")
            try:
                return Money(Decimal(v))
            except InvalidOperation as e:
                raise MoneyError(f"Cannot parse money from string: {value}") from e
        raise MoneyError(f"Unsupported type for money: {type(value).__name__}")

    @staticmethod
    def zero() -> "Money":
        return Money(Decimal("0.00"))

    # --- Basic ops ---
    def _check_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise MoneyError("Currency mismatch")

    def __add__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __mul__(self, multiplier: int | Decimal) -> "Money":
        if isinstance(multiplier, int):
            m = Decimal(multiplier)
        elif isinstance(multiplier, Decimal):
            m = multiplier
        else:
            raise MoneyError("Multiplier must be int or Decimal")
        return Money(self.amount * m, self.currency)

    # --- Discounts ---
    def percent_off(self, percent: Decimal) -> "Money":
        """
        percent: например Decimal("0.15") для 15%
        """
        if percent < 0 or percent > 1:
            raise MoneyError("Percent must be between 0 and 1")
        factor = Decimal("1") - percent
        return Money(self.amount * factor, self.currency)

    def fixed_off(self, discount: "Money", *, floor_zero: bool = True) -> "Money":
        self._check_currency(discount)
        result = self.amount - discount.amount
        if floor_zero and result < 0:
            result = Decimal("0.00")
        return Money(result, self.currency)

    # --- Comparisons (for sorting/filtering) ---
    def __lt__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        self._check_currency(other)
        return self.amount >= other.amount

    # --- Convenience ---
    def is_zero(self) -> bool:
        return self.amount == Decimal("0.00")

    def __str__(self) -> str:
        # "1234.50 RUB"
        return f"{self.amount:.2f} {self.currency}"