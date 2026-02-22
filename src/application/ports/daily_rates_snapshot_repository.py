from __future__ import annotations

from typing import Protocol

from src.domain.entities.rate import DailyRate


class DailyRatesSnapshotRepository(Protocol):
    def replace_all(self, rows: list[DailyRate]) -> None:
        ...
