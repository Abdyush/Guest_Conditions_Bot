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
    """
    Offer = условия применимости + скидка.

    Применимость зависит от:
    - окна проживания (stay) — конкретный подпериод внутри большой доступности
    - сегодняшней даты бронирования (booking_date) — чтобы не показывать то, что нельзя забронировать сейчас
    - категории/тарифа (если оффер ограничен ими)
    """
    id: str
    title: str
    description: str
    discount: Discount

    # Проживание должно целиком входить хотя бы в один из этих периодов
    stay_periods: Sequence[DateRange]

    # Если задан — booking_date должен попадать внутрь
    booking_period: Optional[DateRange] = None

    # Минимальное число ночей (если задано)
    min_nights: Optional[int] = None

    # Ограничения по категории/тарифу (если заданы)
    categories: Optional[set[str]] = None
    tariffs: Optional[set[str]] = None

    # Можно ли суммировать с лояльностью
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
        for p in self.stay_periods:
            if not isinstance(p, DateRange):
                raise OfferError("stay_periods must contain DateRange")

        if self.booking_period is not None and not isinstance(self.booking_period, DateRange):
            raise OfferError("booking_period must be DateRange or None")

        if self.min_nights is not None:
            if not isinstance(self.min_nights, int) or self.min_nights <= 0:
                raise OfferError("min_nights must be int > 0 if provided")

        if self.categories is not None:
            if not isinstance(self.categories, set) or any((not isinstance(x, str) or not x.strip()) for x in self.categories):
                raise OfferError("categories must be set[str] with non-empty strings")

        if self.tariffs is not None:
            if not isinstance(self.tariffs, set) or any((not isinstance(x, str) or not x.strip()) for x in self.tariffs):
                raise OfferError("tariffs must be set[str] with non-empty strings")

        if not isinstance(self.loyalty_compatible, bool):
            raise OfferError("loyalty_compatible must be bool")

    def is_bookable(self, booking_date: date) -> bool:
        """
        Можно ли использовать оффер сегодня (или в указанную дату бронирования).
        Если booking_period не задан — считаем, что бронировать можно всегда.
        """
        if self.booking_period is None:
            return True
        return self.booking_period.contains(booking_date)

    def is_applicable(
        self,
        stay: DateRange,
        *,
        booking_date: date,
        category_id: str,
        tariff_code: str,
    ) -> bool:
        """
        Проверяет применимость оффера к конкретному окну проживания stay.

        Важно:
        - booking_date обязателен: если сегодня не в booking_period — оффер не применим
        - category_id/tariff_code обязательны: иначе нельзя корректно проверить ограничения
        """

        # 0) можно ли бронировать в booking_date
        if not self.is_bookable(booking_date):
            return False

        # 1) минимальные ночи
        if self.min_nights is not None and stay.nights < self.min_nights:
            return False

        # 2) категория
        if self.categories is not None and category_id not in self.categories:
            return False

        # 3) тариф
        if self.tariffs is not None and tariff_code not in self.tariffs:
            return False

        # 4) stay целиком должен попасть хотя бы в один разрешённый stay_period
        for p in self.stay_periods:
            if p.start <= stay.start and stay.end <= p.end:
                return True

        return False