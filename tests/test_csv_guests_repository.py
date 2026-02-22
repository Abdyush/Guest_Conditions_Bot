from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyStatus
from src.infrastructure.repositories.csv_guests_repository import CsvGuestsRepository


def test_csv_guests_repository_parses_three_guests():
    repo = CsvGuestsRepository(guests_csv_path="data/guest_details.csv")
    guests = repo.get_active_guests()

    assert len(guests) == 3

    g1 = next(x for x in guests if x.guest_id == "G1")
    assert g1.allowed_groups == {"DELUXE"}
    assert g1.occupancy.adults == 2
    assert g1.occupancy.children_4_13 == 1
    assert g1.occupancy.infants == 0
    assert g1.loyalty_status == LoyaltyStatus.BRONZE
    assert g1.bank_status is None
    assert g1.desired_price_per_night.amount_minor == 82_900_000

    g2 = next(x for x in guests if x.guest_id == "G2")
    assert g2.allowed_groups == {"ROYAL_SUITE", "VILLA"}
    assert g2.bank_status == BankStatus.SBER_PREMIER
    assert g2.loyalty_status is None

    g3 = next(x for x in guests if x.guest_id == "G3")
    assert g3.allowed_groups is None
    assert g3.loyalty_status == LoyaltyStatus.GOLD
    assert g3.bank_status is None
