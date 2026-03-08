from __future__ import annotations

from decimal import Decimal

from src.domain.value_objects.discount import PercentOff
from src.infrastructure.selenium.offers_transform import map_legacy_scraped_offers_to_domain


def test_map_legacy_scraped_offers_to_domain() -> None:
    scraped = [
        {
            "Название": "Тестовый оффер",
            "Категория": ["Deluxe Mountain View"],
            "Даты проживания": [["01.06.2026", "10.06.2026"]],
            "Даты бронирования": [["01.05.2026", "31.05.2026"]],
            "Формула расчета": "N = C*0.8",
            "Минимальное количество дней": "3",
            "Суммируется с программой лояльности": True,
            "Текст предложения": "Скидка 20%",
        }
    ]

    offers = map_legacy_scraped_offers_to_domain(
        scraped,
        category_to_group={"Deluxe Mountain View": "DELUXE"},
        fail_fast=True,
    )

    assert len(offers) == 1
    offer = offers[0]
    assert offer.min_nights == 3
    assert offer.booking_period is not None
    assert offer.allowed_categories == {"Deluxe Mountain View"}
    assert offer.allowed_groups == {"DELUXE"}
    assert offer.loyalty_compatible is True
    assert isinstance(offer.discount, PercentOff)
    assert offer.discount.percent == Decimal("0.2")
