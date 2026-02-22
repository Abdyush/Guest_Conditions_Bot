from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.offer import Offer


class OffersRepository(Protocol):
    def get_offers(self, today: date) -> list[Offer]:
        ...
