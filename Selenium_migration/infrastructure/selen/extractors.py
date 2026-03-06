# infrastructure/selenium/extractors.py
from selenium.webdriver.remote.webdriver import WebDriver
from core.entities import RoomCategory, RegularPrice

def extract_regular_prices(browser: WebDriver, date) -> list[RegularPrice]:
    """
    Собирает данные с карточки категории и возвращает список RegularPrice,
    НЕ пишет в базу данных.
    """
    print(f"[trace] extract_regular_prices start date={date}")
    # Название категории
    try:
        name = [
            x.text for x in browser.find_elements(
                "css selector", 'div[tl-id="plate-title"]'
            ) if x.text != ''
        ][0]
    except:
        print("Не удалось найти название категории")
        return []

    category = RoomCategory(name=name)

    # Цены
    prices = [
        int(x.text.replace('\u2009', ''))
        for x in browser.find_elements("css selector", 'span.numeric')
        if x.text != ''
    ]

    if len(prices) < 2:
        print(f"{name}: найдено меньше двух цен")
        return []

    only_breakfast = prices[0]
    full_pansion = prices[1]

    # Для каждой категории создаём объект RegularPrice
    return [
        RegularPrice(
            category=category,
            date=date,
            only_breakfast=only_breakfast,
            full_pansion=full_pansion,
            is_last_room=False
        )
    ]

