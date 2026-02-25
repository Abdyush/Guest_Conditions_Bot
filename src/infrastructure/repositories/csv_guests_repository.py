from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from src.application.ports.guests_repository import GuestsRepository
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.category_capacity import Occupancy
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyStatus
from src.domain.value_objects.money import Money


def _csv_reader(path: Path) -> csv.DictReader:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    return csv.DictReader(StringIO(text), delimiter=";")


def _parse_allowed_groups(raw: str | None) -> set[str] | None:
    text = (raw or "").strip()
    if not text:
        return None
    groups = {x.strip().upper() for x in text.split(",") if x.strip()}
    return groups or None


def _parse_loyalty(value: str | None) -> LoyaltyStatus | None:
    raw = (value or "").strip().upper()
    if not raw:
        return None
    try:
        return LoyaltyStatus(raw.lower())
    except ValueError:
        return None


def _parse_bank(value: str | None) -> BankStatus | None:
    raw = (value or "").strip().upper()
    if not raw:
        return None
    try:
        return BankStatus(raw)
    except ValueError:
        return None


class CsvGuestsRepository(GuestsRepository):
    def __init__(self, *, guests_csv_path: str | Path):
        self._guests_csv_path = Path(guests_csv_path)

    def get_active_guests(self) -> list[GuestPreferences]:
        guests: list[GuestPreferences] = []

        for row in _csv_reader(self._guests_csv_path):
            bank_status = _parse_bank(row.get("bank_status"))
            loyalty_status = _parse_loyalty(row.get("loyalty_status"))
            if bank_status is not None:
                loyalty_status = None

            guests.append(
                GuestPreferences(
                    desired_price_per_night=Money.from_minor(
                        int((row.get("desired_price_minor") or "0").strip() or "0"),
                        currency=(row.get("currency") or "RUB").strip() or "RUB",
                    ),
                    loyalty_status=loyalty_status,
                    bank_status=bank_status,
                    allowed_groups=_parse_allowed_groups(row.get("allowed_groups")),
                    occupancy=Occupancy(
                        adults=int((row.get("adults") or "1").strip()),
                        children_4_13=int((row.get("teens_4_13") or "0").strip()),
                        infants=int((row.get("infants_0_3") or "0").strip()),
                    ),
                    guest_id=(row.get("guest_id") or "").strip() or None,
                    guest_name=(row.get("name") or "").strip() or None,
                    guest_phone=(row.get("phone") or "").strip() or None,
                )
            )
        return guests
