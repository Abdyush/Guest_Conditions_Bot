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
        print(f"На странице найдено {count_offer} карточки с офферами")
        offers: list[dict[str, Any]] = []

        for idx in range(count_offer):
            print("")
            print(f"Обрабатываем {idx + 1} карточку из {count_offer}")
            should_stop = False
            try:
                click_offer_card(self._browser, idx)
                time.sleep(3)
                parsed = collect_offer_data(self._browser)
                if isinstance(parsed, dict) and parsed:
                    offers.append(parsed)
                else:
                    print("[warn] collect_offer_data returned empty payload")
            except Exception as exc:
                print(f"[error] failed to process offer card {idx + 1}: {self._short_error_text(exc)}")
            finally:
                try:
                    back_to_all_offers(self._browser)
                    time.sleep(3)
                except Exception as exc:
                    print(f"[error] back_to_all_offers failed: {self._short_error_text(exc)}")
                    should_stop = True
            if should_stop:
                break

        print("")
        print(f"Найдено и обработано офферов: {len(offers)} из {count_offer}")
        print("")
        print("Итоги:")
        for index, offer in enumerate(offers, start=1):
            self._print_offer_summary(index, offer)
        return offers

    @staticmethod
    def _short_error_text(exc: Exception) -> str:
        text = str(exc).strip()
        if not text:
            return "<empty error>"
        return text.splitlines()[0].strip()

    @staticmethod
    def _value(offer: dict[str, Any], key: str) -> Any:
        return offer.get(key)

    @classmethod
    def _print_offer_summary(cls, index: int, offer: dict[str, Any]) -> None:
        print(f"{index}.")
        print(f"Название: {cls._value(offer, 'Название')}")
        print(f"Категория: {cls._value(offer, 'Категория')}")
        print(f"Период проживания: {cls._value(offer, 'Даты проживания')}")
        print(f"Период бронирования: {cls._value(offer, 'Даты бронирования')}")
        print(f"Формула расчета: {cls._value(offer, 'Формула расчета')}")
        print(f"Минимальное количество дней: {cls._value(offer, 'Минимальное количество дней')}")
        print(f"Суммируется с программой лояльности: {cls._value(offer, 'Суммируется с программой лояльности')}")
        print("")
