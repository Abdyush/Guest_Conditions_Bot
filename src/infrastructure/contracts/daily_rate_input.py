from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True, slots=True)
class DailyRateInput:
    date: date
    category_name: Optional[str] = None
    group_id: Optional[str] = None
    tariff_code: str = ""
    adults_count: int = 1
    amount_minor: int = 0
    currency: str = "RUB"
    is_last_room: bool = False
    source: Optional[str] = None
    # Backward-compatible alias.
    category_id: Optional[str] = None
