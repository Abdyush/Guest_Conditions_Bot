from __future__ import annotations

from datetime import date

from src.application.ports.offers_source import OffersSourcePort
from src.domain.entities.offer import Offer
from src.infrastructure.loaders.category_rules_loader import load_category_rules
from src.infrastructure.selenium.browser import build_chrome_options
from src.infrastructure.selenium.offers_gateway import SeleniumLegacyOffersGateway
from src.infrastructure.selenium.offers_transform import map_legacy_scraped_offers_to_domain


class SeleniumOffersSource(OffersSourcePort):
    def __init__(
        self,
        *,
        category_rules_csv_path: str,
        headless: bool = True,
        wait_seconds: int = 20,
        fail_fast: bool = False,
    ):
        self._category_rules_csv_path = category_rules_csv_path
        self._headless = headless
        self._wait_seconds = wait_seconds
        self._fail_fast = fail_fast

    def get_offers(self, today: date) -> list[Offer]:
        _ = today
        try:
            from selenium import webdriver
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "Selenium is required for offers-source=selenium. Install `selenium` and ChromeDriver."
            ) from exc

        category_to_group, _, _ = load_category_rules(self._category_rules_csv_path)
        options = build_chrome_options(headless=self._headless)
        with webdriver.Chrome(options=options) as browser:
            gateway = SeleniumLegacyOffersGateway(browser, wait_seconds=self._wait_seconds)
            scraped = gateway.get_all_offers()
        return map_legacy_scraped_offers_to_domain(
            scraped,
            category_to_group=category_to_group,
            fail_fast=self._fail_fast,
        )
