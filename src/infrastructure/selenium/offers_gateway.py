from __future__ import annotations

import time
from typing import Any

from selenium.webdriver.remote.webdriver import WebDriver

from src.infrastructure.selenium.legacy_offers.offers_funcs import (
    back_to_all_offers,
    click_offer_card,
    collect_offer_data,
    find_offer_cards,
)


class SeleniumLegacyOffersGateway:
    def __init__(self, browser: WebDriver, *, wait_seconds: int = 20):
        self._browser = browser
        self._wait_seconds = wait_seconds

    def _open_offers_page(self) -> None:
        self._browser.get("https://mriyaresort.com/offers/")
        time.sleep(5)

    def get_all_offers(self) -> list[dict[str, Any]]:
        self._open_offers_page()
        count_offer = find_offer_cards(self._browser)
        print(f"[trace] SeleniumLegacyOffersGateway: found {count_offer} offers")
        offers: list[dict[str, Any]] = []

        for idx in range(count_offer):
            print(f"[trace] processing offer card {idx + 1}/{count_offer}")
            should_stop = False
            try:
                click_offer_card(self._browser, idx)
                time.sleep(3)
                parsed = collect_offer_data(self._browser)
                if isinstance(parsed, dict) and parsed:
                    offers.append(parsed)
                    print("[trace] offer collected")
                else:
                    print("[warn] collect_offer_data returned empty payload")
            except Exception as exc:
                print(f"[error] failed to process offer card {idx}: {exc}")
            finally:
                try:
                    back_to_all_offers(self._browser)
                    time.sleep(3)
                except Exception as exc:
                    print(f"[error] back_to_all_offers failed: {exc}")
                    should_stop = True
            if should_stop:
                break

        print(f"[trace] SeleniumLegacyOffersGateway: parsed={len(offers)}")
        return offers
