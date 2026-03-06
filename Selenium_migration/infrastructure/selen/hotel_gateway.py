from datetime import date
import time
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from core.ports import HotelSiteGateway
from core.entities import RegularPrice
from .extractors import extract_regular_prices
from parser.funcs.prices_funcs import (
    find_btn, switch_dates, find_categories, check_last_room
)

class SeleniumHotelGateway(HotelSiteGateway):
    def __init__(self, browser: WebDriver):
        print("[trace] SeleniumHotelGateway.__init__ start")
        self.browser = browser
        self._open_site()

    def _open_site(self):
        print("[trace] SeleniumHotelGateway._open_site start")
        btn = find_btn(self.browser)
        btn.click()
        time.sleep(5)
        
    def get_regular_prices_for_date(self, dt: date) -> list[RegularPrice]:
        print(f"[trace] get_regular_prices_for_date start dt={dt}")
        switch_dates(self.browser, dt)
        
        time.sleep(4)

        categories = []
        count_available_categories = 0
        for attempt in range(4):
            categories = find_categories(self.browser)
            count_available_categories = len(categories)
            if count_available_categories > 0:
                break
            if attempt < 3:
                print(f"[trace] категории не загрузились, пробуем снова ({attempt + 2}/4)")
                time.sleep(4)
        print(f'На {dt.strftime("%d.%m.%Y")} найдено: {count_available_categories} доступных категорий')
        results = []

        for i in range(count_available_categories):
            time.sleep(3)
            cat_element = None
            for attempt in range(4):
                if attempt > 0:
                    time.sleep(4)
                    categories = find_categories(self.browser)

                if i >= len(categories):
                    if attempt < 3:
                        print(f"[trace] категория {i+1} пока не появилась, пробуем снова ({attempt + 1}/4)")
                        continue
                    print(f'{i+1} категория из списка недоступна')
                    break

                try:
                    cat_element = categories[i]
                    self.browser.execute_script("arguments[0].scrollIntoView(true);", cat_element)
                    WebDriverWait(self.browser, 10).until(EC.element_to_be_clickable(cat_element))
                    print(f'Выбрал {i+1} категорию из {count_available_categories} найденных')
                    break
                except Exception:
                    if attempt < 3:
                        print(f'{i+1} категория из списка недоступна, повторяем ({attempt + 2}/4)')
                        continue
                    print(f'{i+1} категория из списка недоступна')
                    break

            if not cat_element:
                continue
        
            last_room = check_last_room(cat_element)
            
            # Переход на страницу категории
            self.browser.execute_script("arguments[0].click();", cat_element)
            print(f'Переходим в категорию {i+1} из списка и спим 4 секунды')
            time.sleep(4)
            
            # Сбор цен
            items = extract_regular_prices(self.browser, dt)

            # Проставим признак "последний номер"
            for item in items:
                item.is_last_room = last_room

            results.extend(items)

            # Кнопка "назад"
            back_btn = self.browser.find_element(By.CLASS_NAME, 'x-hnp__link')
            WebDriverWait(self.browser, 10).until(EC.element_to_be_clickable(back_btn))
            self.browser.execute_script("arguments[0].click();", back_btn)
            print(f'Нашел кнопку возврата к выбору категорий и кликнул по ней, спим 3 секунды')
            # TODO: Оптимизировать ожидание
            time.sleep(3)
            categories = find_categories(self.browser)

        return results
