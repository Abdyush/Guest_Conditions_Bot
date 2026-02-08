from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from src.domain.value_objects.money import Money


class DiscountError(ValueError):
    pass


class FreeNightSelection(str, Enum):
    CHEAPEST = "cheapest"
    # BY_ORDER можно добавить позже, когда появится точное правило
    # BY_ORDER = "by_order"


@dataclass(frozen=True, slots=True)
class DiscountResult:
    total_before: Money
    discount_amount: Money
    total_after: Money
    label: str


def _sum_money(values: list[Money]) -> Money:
    total = Money.zero()
    for m in values:
        total = total + m
    return total


class Discount:
    """
    Скидка применяется к набору ночей (nightly_prices) и возвращает итог.
    Никаких "free nights" в результат не отдаём — это деталь расчёта, не UI.
    """
    def apply(self, nightly_prices: list[Money]) -> DiscountResult:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class PercentOff(Discount):
    """
    percent = Decimal("0.30") означает -30%
    """
    percent: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.percent, Decimal):
            raise DiscountError("percent must be Decimal")
        if self.percent < 0 or self.percent > 1:
            raise DiscountError("percent must be between 0 and 1")

    def apply(self, nightly_prices: list[Money]) -> DiscountResult:
        total_before = _sum_money(nightly_prices)
        total_after = total_before.percent_off(self.percent)
        discount_amount = total_before - total_after
        pct = int((self.percent * Decimal("100")).quantize(Decimal("1")))
        return DiscountResult(
            total_before=total_before,
            discount_amount=discount_amount,
            total_after=total_after,
            label=f"{pct}% off",
        )


@dataclass(frozen=True, slots=True)
class FixedOff(Discount):
    """
    Фиксированная скидка с итоговой суммы.
    """
    amount: Money
    floor_zero: bool = True

    def apply(self, nightly_prices: list[Money]) -> DiscountResult:
        total_before = _sum_money(nightly_prices)
        total_after = total_before.fixed_off(self.amount, floor_zero=self.floor_zero)
        discount_amount = total_before - total_after
        return DiscountResult(
            total_before=total_before,
            discount_amount=discount_amount,
            total_after=total_after,
            label=f"fixed off {self.amount}",
        )


@dataclass(frozen=True, slots=True)
class PayXGetY(Discount):
    """
    "Y ночей по цене X" (пример: 4=3 => PayXGetY(3,4)).
    Если ценники по ночам разные, мы считаем, что бесплатные ночи — самые дешёвые.
    Это влияет только на итог (и effective_per_night), но не требует показывать "free night".
    """
    pay_nights: int
    get_nights: int
    selection: FreeNightSelection = FreeNightSelection.CHEAPEST

    def __post_init__(self) -> None:
        if self.pay_nights <= 0:
            raise DiscountError("pay_nights must be > 0")
        if self.get_nights <= 0:
            raise DiscountError("get_nights must be > 0")
        if self.pay_nights >= self.get_nights:
            raise DiscountError("pay_nights must be < get_nights")

    def apply(self, nightly_prices: list[Money]) -> DiscountResult:
        total_before = _sum_money(nightly_prices)
        n = len(nightly_prices)

        if n < self.get_nights:
            return DiscountResult(
                total_before=total_before,
                discount_amount=Money.zero(),
                total_after=total_before,
                label=f"Pay {self.pay_nights} get {self.get_nights} (not applied)",
            )

        gift_per_block = self.get_nights - self.pay_nights
        blocks = n // self.get_nights
        gift_nights = blocks * gift_per_block

        if gift_nights <= 0:
            return DiscountResult(
                total_before=total_before,
                discount_amount=Money.zero(),
                total_after=total_before,
                label=f"Pay {self.pay_nights} get {self.get_nights} (not applied)",
            )

        if self.selection == FreeNightSelection.CHEAPEST:
            # скидка = сумма gift_nights самых дешёвых ночей
            sorted_prices = sorted(nightly_prices)  # Money сравним
            discount_amount = _sum_money(sorted_prices[:gift_nights])
        else:
            # заготовка под другие стратегии
            sorted_prices = sorted(nightly_prices)
            discount_amount = _sum_money(sorted_prices[:gift_nights])

        total_after = total_before.fixed_off(discount_amount, floor_zero=True)

        return DiscountResult(
            total_before=total_before,
            discount_amount=discount_amount,
            total_after=total_after,
            label=f"Pay {self.pay_nights} get {self.get_nights}",
        )