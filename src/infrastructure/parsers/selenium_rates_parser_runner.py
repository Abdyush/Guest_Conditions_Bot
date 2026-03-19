from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
from src.infrastructure.selenium.rates_parallel_runner import RatesParallelRunConfig, SeleniumRatesParallelRunner


@dataclass(frozen=True, slots=True)
class SeleniumRatesParserRunner:
    rules_repo: PostgresRulesRepository
    headless: bool = True
    wait_seconds: int = 20

    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int:
        config = RatesParallelRunConfig(
            category_to_group=self.rules_repo.get_category_to_group(),
            adults_counts=adults_counts,
            days_to_collect=days_to_collect,
            headless=self.headless,
            wait_seconds=self.wait_seconds,
        )
        runner = SeleniumRatesParallelRunner(config)
        rates = runner.run(start_date=start_date)
        repo = PostgresDailyRatesRepository()
        repo.replace_all(rates)
        return len(rates)
