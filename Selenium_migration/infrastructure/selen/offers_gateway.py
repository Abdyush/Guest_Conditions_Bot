# infrastructure/selen/offers_gateway.py
import time
import uuid
from typing import List, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from core.entities import SpecialOffer, StayPeriod, BookingPeriod
from core.ports import OffersSiteGateway
from parser.funcs.offers_funcs import (
    find_offer_cards,
    click_offer_card,
    back_to_all_offers,
    collect_offer_data,
)
from parser.funcs.common_funcs import parse_date


class SeleniumOfferGateway(OffersSiteGateway):
    def __init__(self, browser: WebDriver):
        self.browser = browser
        self._open_offers_page()

    def _open_offers_page(self) -> None:
        # РОВНО как в старом parser_offers_main
        self.browser.get("https://mriyaresort.com/offers/")
        time.sleep(5)  # оставляем твой экспериментальный sleep

    def get_all_offers(self) -> List[SpecialOffer]:
        offers: List[SpecialOffer] = []

        count_offer = find_offer_cards(self.browser)
        print(f"[trace] SeleniumOfferGateway: found {count_offer} offers")

        for i in range(count_offer):
            print(f"[trace] processing offer card {i + 1} / {count_offer}")
            try:
                click_offer_card(self.browser, i)
                print(f"[trace] clicked card {i + 1}")
            except Exception as e:
                print(f"[error] click_offer_card({i}) failed: {e}")
                continue

            time.sleep(3)  # как в старом коде

            offer_dict = collect_offer_data(self.browser)
            if offer_dict:
                entity = self._map_offer_dict_to_entity(offer_dict)
                if entity.stay_periods:
                    offers.append(entity)
                else:
                    print("[warn] offer has no valid stay periods, skipped")

            # Возврат к списку офферов
            try:
                back_to_all_offers(self.browser)
                print("[trace] back_to_all_offers")
            except Exception as e:
                print(f"[error] back_to_all_offers failed: {e}")
                break

            time.sleep(3)  # как в старом коде

        return offers

    # ---------- Маппинг dict -> SpecialOffer ----------

    def _map_offer_dict_to_entity(self, data: dict) -> SpecialOffer:
        title = data.get("Название", "").strip()
        text = data.get("Текст предложения", "").strip()

        # категории: может быть строка, список или None
        raw_categories = data.get("Категория") or []
        if isinstance(raw_categories, str):
            categories = [raw_categories]
        else:
            categories = list(raw_categories)

        # периоды проживания
        stay_periods: List[StayPeriod] = []
        for stay_range in data.get("Даты проживания", []):
            try:
                start = parse_date(stay_range[0])
                end = parse_date(stay_range[1])
                if start > end:
                    print(f"[warn] invalid stay period {stay_range}: {start} > {end}")
                    continue
                stay_periods.append(StayPeriod(start=start, end=end))
            except Exception as e:
                print(f"[error] stay_range {stay_range}: {e}")

        # период бронирования (у тебя он всегда один, если есть)
        booking_period = self._extract_booking_period(data)

        # формула и мин. дни
        formula = data.get("Формула расчета")
        min_days_raw = data.get("Минимальное количество дней")
        min_days: Optional[int]
        try:
            min_days = int(str(min_days_raw).strip()) if min_days_raw is not None else None
        except Exception:
            min_days = None

        loyalty = data.get("Суммируется с программой лояльности", None)
        if loyalty is not None:
            loyalty = bool(loyalty)

        return SpecialOffer(
            id=uuid.uuid4(),
            title=title,
            text=text,
            categories=categories,
            stay_periods=stay_periods,
            booking_period=booking_period,
            formula=formula,
            min_days=min_days,
            loyalty_compatible=loyalty,
        )

    def _extract_booking_period(self, data: dict) -> Optional[BookingPeriod]:
        booking_list = data.get("Даты бронирования") or []
        if not booking_list:
            return None

        # у тебя там список с одним диапазоном: [(start, end)] или [[start, end]]
        raw = booking_list[0]
        try:
            start_str, end_str = raw
            start = parse_date(start_str)
            end = parse_date(end_str)
            if start > end:
                print(f"[warn] invalid booking period {raw}: {start} > {end}")
                return None
            return BookingPeriod(start=start, end=end)
        except Exception as e:
            print(f"[error] booking period {raw}: {e}")
            return None