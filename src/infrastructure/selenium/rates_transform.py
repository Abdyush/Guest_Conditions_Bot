from __future__ import annotations

from collections.abc import Iterable

from src.domain.entities.rate import DailyRate
from src.domain.value_objects.money import Money
from src.infrastructure.selenium.contracts import ScrapedCategoryRate


def _normalize_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def build_group_mapping(category_to_group: dict[str, str]) -> dict[str, str]:
    return {_normalize_key(category): group for category, group in category_to_group.items()}


def map_scraped_rates_to_domain(
    scraped_rates: Iterable[ScrapedCategoryRate],
    *,
    category_to_group: dict[str, str],
    adults_counts: Iterable[int],
) -> list[DailyRate]:
    normalized_mapping = build_group_mapping(category_to_group)
    adults = sorted(set(adults_counts))
    if not adults:
        raise ValueError("adults_counts must not be empty")

    out: list[DailyRate] = []
    for row in scraped_rates:
        key = _normalize_key(row.category_name)
        group_id = normalized_mapping.get(key, row.category_name)

        for adults_count in adults:
            out.append(
                DailyRate(
                    date=row.date,
                    category_id=row.category_name,
                    group_id=group_id,
                    tariff_code="breakfast",
                    adults_count=adults_count,
                    price=Money.from_minor(row.breakfast_minor, currency="RUB"),
                    is_available=True,
                    is_last_room=row.is_last_room,
                )
            )
            out.append(
                DailyRate(
                    date=row.date,
                    category_id=row.category_name,
                    group_id=group_id,
                    tariff_code="fullpansion",
                    adults_count=adults_count,
                    price=Money.from_minor(row.full_pansion_minor, currency="RUB"),
                    is_available=True,
                    is_last_room=row.is_last_room,
                )
            )

    return out
