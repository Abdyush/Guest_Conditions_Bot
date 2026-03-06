from __future__ import annotations

from datetime import date, timedelta

from src.application.ports.daily_rates_source import DailyRatesSourcePort
from src.domain.entities.rate import DailyRate
from src.infrastructure.loaders.category_rules_loader import load_category_rules
from src.infrastructure.selenium.browser import build_chrome_options
from src.infrastructure.selenium.hotel_rates_gateway import SeleniumHotelRatesGateway
from src.infrastructure.selenium.rates_transform import map_scraped_rates_to_domain


class SeleniumDailyRatesSource(DailyRatesSourcePort):
    def __init__(
        self,
        *,
        category_rules_csv_path: str,
        adults_counts: list[int],
        headless: bool = True,
        wait_seconds: int = 20,
    ):
        self._category_rules_csv_path = category_rules_csv_path
        self._adults_counts = adults_counts
        self._headless = headless
        self._wait_seconds = wait_seconds

    def get_daily_rates(self, date_from: date, date_to: date) -> list[DailyRate]:
        if date_to < date_from:
            raise ValueError("date_to must be >= date_from")

        try:
            from selenium import webdriver
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "Selenium is required for rates-source=selenium. Install `selenium` and ChromeDriver."
            ) from exc

        category_to_group, _, _ = load_category_rules(self._category_rules_csv_path)
        options = build_chrome_options(headless=self._headless)
        parsed: list[DailyRate] = []

        with webdriver.Chrome(options=options) as browser:
            gateway = SeleniumHotelRatesGateway(browser, wait_seconds=self._wait_seconds)
            current = date_from
            while current <= date_to:
                scraped = gateway.get_rates_for_date(current)
                parsed.extend(
                    map_scraped_rates_to_domain(
                        scraped,
                        category_to_group=category_to_group,
                        adults_counts=self._adults_counts,
                    )
                )
                current += timedelta(days=1)

        return parsed
