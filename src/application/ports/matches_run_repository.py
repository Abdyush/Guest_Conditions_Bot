from __future__ import annotations

from typing import Protocol

from src.application.dto.matched_date_record import MatchedDateRecord


class MatchesRunRepository(Protocol):
    def replace_run(self, run_id: str, rows: list[MatchedDateRecord]) -> None:
        ...

    def get_run_rows(self, run_id: str) -> list[MatchedDateRecord]:
        ...

    def get_latest_run_id(self) -> str | None:
        ...
