from __future__ import annotations

import os

from sqlalchemy import BIGINT, INTEGER, TEXT, Column, MetaData, Table, create_engine, select, text
from sqlalchemy.engine import Engine

from src.application.ports.guests_repository import GuestsRepository
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.category_capacity import Occupancy
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyStatus
from src.domain.value_objects.money import Money


metadata = MetaData()

guests_table = Table(
    "guest_details",
    metadata,
    Column("guest_id", TEXT, primary_key=True),
    Column("name", TEXT, nullable=True),
    Column("desired_price_minor", BIGINT, nullable=False),
    Column("currency", TEXT, nullable=False),
    Column("allowed_groups", TEXT, nullable=True),
    Column("adults", INTEGER, nullable=False),
    Column("teens_4_13", INTEGER, nullable=False),
    Column("infants_0_3", INTEGER, nullable=False),
    Column("loyalty_status", TEXT, nullable=True),
    Column("bank_status", TEXT, nullable=True),
)


def _serialize_groups(groups: set[str] | None) -> str | None:
    if not groups:
        return None
    return ",".join(sorted(groups))


def _parse_groups(raw: str | None) -> set[str] | None:
    text_value = (raw or "").strip()
    if not text_value:
        return None
    values = {x.strip().upper() for x in text_value.split(",") if x.strip()}
    return values or None


class PostgresGuestsRepository(GuestsRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresGuestsRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)

    def replace_all(self, guests: list[GuestPreferences]) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE guest_details"))
            if not guests:
                return
            conn.execute(
                guests_table.insert(),
                [
                    {
                        "guest_id": guest.guest_id or "",
                        "name": guest.guest_name,
                        "desired_price_minor": guest.desired_price_per_night.amount_minor,
                        "currency": guest.desired_price_per_night.currency,
                        "allowed_groups": _serialize_groups(guest.effective_allowed_groups),
                        "adults": guest.occupancy.adults,
                        "teens_4_13": guest.occupancy.children_4_13,
                        "infants_0_3": guest.occupancy.infants,
                        "loyalty_status": guest.loyalty_status.value.upper() if guest.loyalty_status else None,
                        "bank_status": guest.bank_status.value if guest.bank_status else None,
                    }
                    for guest in guests
                ],
            )

    def get_active_guests(self) -> list[GuestPreferences]:
        stmt = select(guests_table)
        out: list[GuestPreferences] = []
        with self._engine.connect() as conn:
            for row in conn.execute(stmt).mappings():
                bank_status = BankStatus(row["bank_status"]) if row["bank_status"] else None
                loyalty_status = None
                if bank_status is None and row["loyalty_status"]:
                    loyalty_status = LoyaltyStatus(row["loyalty_status"].lower())

                out.append(
                    GuestPreferences(
                        desired_price_per_night=Money.from_minor(int(row["desired_price_minor"]), currency=row["currency"]),
                        loyalty_status=loyalty_status,
                        bank_status=bank_status,
                        allowed_groups=_parse_groups(row["allowed_groups"]),
                        occupancy=Occupancy(
                            adults=int(row["adults"]),
                            children_4_13=int(row["teens_4_13"]),
                            infants=int(row["infants_0_3"]),
                        ),
                        guest_id=(row["guest_id"] or None),
                        guest_name=(row["name"] or None),
                    )
                )
        return out
