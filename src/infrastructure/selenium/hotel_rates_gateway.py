from __future__ import annotations

import time
from datetime import date, timedelta

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.infrastructure.selenium.contracts import ScrapedCategoryRate


def _find_calendar_root(frame):
    return frame.find_element(By.XPATH, "//div[@data-mode]")


def _find_dates_by_month(calendar_root) -> dict[str, list]:
    months = calendar_root.find_elements(By.XPATH, './/div[@data-month]')
    if len(months) < 2:
        raise RuntimeError("Could not read booking calendar months from page")

    data_months = [el.get_attribute("data-month") for el in months]
    return {
        data_months[0][:7]: [d for d in months[0].find_elements(By.XPATH, './/span') if d.text.isdigit()],
        data_months[1][:7]: [d for d in months[1].find_elements(By.XPATH, './/span') if d.text.isdigit()],
    }


def _switch_calendar_month(calendar_root) -> None:
    nav = calendar_root.find_element(By.TAG_NAME, "nav")
    buttons = nav.find_elements(By.TAG_NAME, "button")
    if len(buttons) < 2:
        raise RuntimeError("Calendar month switch button not found")
    buttons[1].click()
    time.sleep(1)


def _find_date_button(dt: date, dates_by_month: dict[str, list], *, checkout: bool):
    target_dt = dt + timedelta(days=1) if checkout else dt
    year_month = target_dt.strftime("%Y-%m")
    day_number = target_dt.day
    month_dates = dates_by_month.get(year_month) or []
    for candidate in month_dates:
        if candidate.text == str(day_number):
            return candidate
    raise RuntimeError(f"Date button not found in calendar: {target_dt.isoformat()}")


class SeleniumHotelRatesGateway:
    def __init__(self, browser: WebDriver, *, adults_count: int = 1, wait_seconds: int = 20):
        if adults_count <= 0:
            raise ValueError("adults_count must be > 0")
        self._browser = browser
        self._adults_count = adults_count
        self._wait = WebDriverWait(browser, wait_seconds)
        self._open_booking_page()

    def _open_booking_page(self) -> None:
        self._browser.get("https://mriyaresort.com/booking/")
        time.sleep(5)

        frame = self._wait.until(EC.presence_of_element_located((By.CLASS_NAME, "block--content")))
        self._browser.execute_script("arguments[0].scrollIntoView(true);", frame)
        form = frame.find_element(By.ID, "tl-booking-form")
        iframes = form.find_elements(By.TAG_NAME, "iframe")
        if len(iframes) < 2:
            raise RuntimeError("Booking iframe not found")

        self._browser.switch_to.frame(iframes[1])  
        container = self._wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page-container")))  
        
        select_adults = container.find_element(By.CLASS_NAME, "x-select__match-icon")
        select_adults.click()
        time.sleep(4)

        adults_dropdown = self._wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.x-sd")))
        time.sleep(1)
        choices = adults_dropdown.find_elements(By.CSS_SELECTOR, "div.x-sd__choice")
        target = next((el for el in choices if str(self._adults_count) in el.text), None)

        if target:
            target.click()
            time.sleep(1)
        else:
            raise RuntimeError(f"Option with {self._adults_count} adults not found")
        
        buttons = container.find_elements(By.TAG_NAME, "span")
        search_button = next((el for el in buttons if el.text.strip() == "Найти"), None)
        if search_button is None:
            raise RuntimeError("Search button not found on booking page")
        search_button.click()
        time.sleep(5)

    def _switch_dates(self, stay_date: date) -> None:
        input_date = self._browser.find_element(By.CLASS_NAME, "x-hcp__text-field")
        input_btn = input_date.find_element(By.TAG_NAME, "input")
        self._browser.execute_script("arguments[0].scrollIntoView(true);", input_btn)
        self._browser.execute_script("arguments[0].click();", input_btn)
        modal = self._browser.find_element(By.CLASS_NAME, "x-modal__container")
        time.sleep(2)

        calendar_root = _find_calendar_root(modal)
        dates = _find_dates_by_month(calendar_root)
        try:
            arrival_btn = _find_date_button(stay_date, dates, checkout=False)
        except RuntimeError:
            _switch_calendar_month(calendar_root)
            calendar_root = _find_calendar_root(modal)
            dates = _find_dates_by_month(calendar_root)
            arrival_btn = _find_date_button(stay_date, dates, checkout=False)
        self._browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", arrival_btn)
        self._wait.until(EC.element_to_be_clickable(arrival_btn)).click()

        checkout_btn = _find_date_button(stay_date, dates, checkout=True)
        self._browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkout_btn)
        self._wait.until(EC.element_to_be_clickable(checkout_btn)).click()

    def _find_categories(self) -> list:
        try:
            self._browser.find_element(By.CSS_SELECTOR,
                                        "[tl-message*='closest_available_dates']")
            return []
        except NoSuchElementException:
            selected_buttons = []
            while True:
                start = len(selected_buttons)
                tmp = [
                    x
                    for x in self._browser.find_elements(By.CLASS_NAME, "tl-btn")
                    if x.text.strip() == "Выбрать"
                ]
                if not tmp:
                    raise RuntimeError("Category buttons with text 'Выбрать' not found on page")
                selected_buttons = list(set(selected_buttons).union(set(tmp)))
                if len(selected_buttons) == start:
                    return selected_buttons
                self._browser.execute_script("arguments[0].scrollIntoView(true);", tmp[-1])
                time.sleep(1)

    @staticmethod
    def _is_last_room(category_button) -> bool:
        try:
            parent = category_button.find_element(By.XPATH, './/ancestor::div[@data-shift-animate="true"]')
            parent.find_element(By.XPATH, './/div[contains(text(), "Остался") and contains(text(), "номер")]')
            return True
        except Exception:
            return False

    def _extract_current_category_rate(self, stay_date: date, *, is_last_room: bool) -> ScrapedCategoryRate | None:
        try:
            names = [
                x.text.strip()
                for x in self._browser.find_elements("css selector", 'div[tl-id="plate-title"]')
                if x.text.strip()
            ]
            category_name = names[0]
        except Exception:
            return None

        prices = []
        for el in self._browser.find_elements("css selector", "span.numeric"):
            text = el.text.strip().replace("\u2009", "")
            if not text:
                continue
            if text.isdigit():
                prices.append(int(text))
        if len(prices) < 2:
            return None

        return ScrapedCategoryRate(
            date=stay_date,
            category_name=category_name,
            breakfast_minor=prices[0] * 100,
            full_pansion_minor=prices[1] * 100,
            is_last_room=is_last_room,
        )

    def get_rates_for_date(self, stay_date: date) -> list[ScrapedCategoryRate]:
        self._switch_dates(stay_date)
        time.sleep(4)

        categories = self._find_categories()
        results: list[ScrapedCategoryRate] = []
        for index in range(len(categories)):
            categories = self._find_categories()
            if index >= len(categories):
                break
            category_button = categories[index]
            last_room = self._is_last_room(category_button)
            self._browser.execute_script("arguments[0].click();", category_button)
            time.sleep(4)

            item = self._extract_current_category_rate(stay_date, is_last_room=last_room)
            if item is not None:
                results.append(item)

            time.sleep(4)
            back_btn = self._browser.find_element(By.CLASS_NAME, "x-hnp__link")
            self._wait.until(EC.element_to_be_clickable(back_btn))
            self._browser.execute_script("arguments[0].click();", back_btn)
            time.sleep(3)

        return results
