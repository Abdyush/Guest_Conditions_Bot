from datetime import date
from pathlib import Path

from src.infrastructure.repositories.csv_offers_repository import CsvOffersRepository


def test_csv_offers_repository_parses_one_offer_with_two_stay_periods():
    tmp_dir = Path(".tmp_tests")
    tmp_dir.mkdir(exist_ok=True)
    csv_path = tmp_dir / "special_offers_test.csv"
    csv_path.write_text(
        "\n".join(
            [
                "id;title;description;discount_type;discount_value;min_nights;stay_periods;booking_period;allowed_groups;allowed_categories;loyalty_compatible",
                "O1;Test Offer;desc;PERCENT;0.10;2;2026-02-01..2026-02-10|2026-03-01..2026-03-05;2026-01-20..2026-03-15;DELUXE,ROYAL_SUITE;;true",
            ]
        ),
        encoding="utf-8",
    )

    repo = CsvOffersRepository(offers_csv_path=csv_path)
    offers = repo.get_offers(today=date(2026, 2, 1))

    assert len(offers) == 1
    offer = offers[0]
    assert offer.id == "O1"
    assert offer.min_nights == 2
    assert len(offer.stay_periods) == 2
    assert offer.stay_periods[0].start == date(2026, 2, 1)
    assert offer.stay_periods[0].end == date(2026, 2, 10)
    assert offer.stay_periods[1].start == date(2026, 3, 1)
    assert offer.stay_periods[1].end == date(2026, 3, 5)
    assert offer.allowed_groups == {"DELUXE", "ROYAL_SUITE"}
    assert offer.loyalty_compatible is True
