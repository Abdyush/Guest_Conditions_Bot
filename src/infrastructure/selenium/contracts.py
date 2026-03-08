from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ScrapedCategoryRate:
    date: date
    category_name: str
    breakfast_minor: int
    full_pansion_minor: int
    is_last_room: bool


@dataclass(frozen=True, slots=True)
class ScrapedOffer:
    source_url: str
    title: str
    text: str
