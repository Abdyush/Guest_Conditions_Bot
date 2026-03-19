from __future__ import annotations

from datetime import date

from src.application.ports.offers_source import OffersSourcePort
from src.domain.entities.offer import Offer
from src.infrastructure.selenium.browser import build_chrome_options
from src.infrastructure.selenium.offers_gateway import SeleniumLegacyOffersGateway
from src.infrastructure.selenium.offers_transform import map_legacy_scraped_offers_to_domain


class SeleniumOffersSource(OffersSourcePort):
    def __init__(
        self,
        *,
        category_to_group: dict[str, str],
        headless: bool = True,
        wait_seconds: int = 20,
        fail_fast: bool = False,
    ):
        if not category_to_group:
            raise ValueError("category_to_group must not be empty; seed category_rules in Postgres first")
        self._category_to_group = dict(category_to_group)
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

        options = build_chrome_options(headless=self._headless)
        with webdriver.Chrome(options=options) as browser:
            gateway = SeleniumLegacyOffersGateway(browser, wait_seconds=self._wait_seconds)
            scraped = gateway.get_all_offers()
        return map_legacy_scraped_offers_to_domain(
            scraped,
            category_to_group=self._category_to_group,
            fail_fast=self._fail_fast,
        )
