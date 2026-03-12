from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
from src.infrastructure.sources.selenium_offers_source import SeleniumOffersSource


@dataclass(frozen=True, slots=True)
class SeleniumOffersParserRunner:
    category_rules_csv_path: str
    headless: bool = True
    wait_seconds: int = 20
    fail_fast: bool = False

    def run(self, *, booking_date: date) -> int:
        source = SeleniumOffersSource(
            category_rules_csv_path=self.category_rules_csv_path,
            headless=self.headless,
            wait_seconds=self.wait_seconds,
            fail_fast=self.fail_fast,
        )
        offers = source.get_offers(booking_date)
        repo = PostgresOffersRepository()
        repo.replace_all(offers)
        return len(offers)
