from __future__ import annotations

from datetime import date as d

from src.infrastructure.selenium.contracts import ScrapedCategoryRate
from src.infrastructure.selenium.rates_transform import map_scraped_rates_to_domain


def test_map_scraped_rates_to_domain_builds_two_tariffs_and_group_mapping() -> None:
    scraped = [
        ScrapedCategoryRate(
            date=d(2026, 3, 1),
            category_name="Deluxe Mountain View",
            breakfast_minor=6_560_000,
            full_pansion_minor=7_290_000,
            is_last_room=True,
        )
    ]
    category_to_group = {"Deluxe Mountain View": "DELUXE"}

    out = map_scraped_rates_to_domain(
        scraped,
        category_to_group=category_to_group,
        adults_counts=[1, 2],
    )

    assert len(out) == 4
    assert {x.tariff_code for x in out} == {"breakfast", "fullpansion"}
    assert {x.adults_count for x in out} == {1, 2}
    assert {x.group_id for x in out} == {"DELUXE"}
    assert all(x.is_last_room for x in out)
