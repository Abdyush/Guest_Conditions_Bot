import json
import time
import os
import re
from datetime import datetime, timedelta
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Keys
from openai import OpenAI
from typing import Union, List, Tuple


# Функция ищет на странице все карточки со специальными предложениями
def find_offer_cards(browser):
    # Сначала проверяем есть ли на странице алерт перекрывающий основные элементы и закрываем его
    try:
        alert = browser.find_element(By.XPATH, "//div[@class='popup--content' and @data-notification='alert']//button[contains(@class, 'button-primary')]")
        alert.click()
        print('На странице обнаружен алерт и успешно закрыт')
    except:
        print('Алерт на странице не обнаружен')
        
    cards = browser.find_elements(By.CLASS_NAME, 'card--action')
    print(f'На странице найдено {len(cards)} карточек с офферами')
    
    return len(cards)
    
    
# Функция скроллящая страницу вниз для прогрузки все элементов и кликающая на карточку    
def click_offer_card(browser, index):
    for _ in range(15):
        # находим блок с тегом html
        block = browser.find_element(By.TAG_NAME, 'html')
        # и как бы поключившись к нему, имитируем нажатие клавиши вниз
        block.send_keys(Keys.DOWN)
        # Спим 1 секунду 
        # TODO: Оптимизировать ожидание
        time.sleep(1)
    print('Проскроллил страницу вниз')
        
    # Зачем то снова находим все карточки, есть ли смысл искть их сверху?    
    cards = browser.find_elements(By.CLASS_NAME, 'card--action')
    
    # Ждем пока карточка станет кликабельной
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(cards[index]))
    # Прокручиваем к кнопке
    browser.execute_script("return arguments[0].scrollIntoView(true);", cards[index])
    print('Проскроллил к карточке')
    
    title = cards[index].get_attribute("title")
    if title == 'Подарочные сертификаты':
        msg = "название 'Подарочные сертификаты', это не спец предложение, возвращаемся на страницу с офферами"
        raise ValueError(msg)
 
    # Кликаем по карточке
    cards[index].click()


# Функция находит и кликает по кнопке возврата по всем офферам    
def back_to_all_offers(browser):
    link_element = browser.find_element(By.CSS_SELECTOR, "a[href='/offers']")
    link_element.click()
    

# Функция для спец предложения "Ранее бронирование", его суть в том, что скидка применяется если гость забронировал номер минимум за 60 суток до заезда
# таким образом, мы форматируем даты проживания прибавляя 60 суток к сегодняшнему дню и определяя переменную -  начало периода спец предложения
def early_booking(living_dates: List[list[str]]) -> List[list[str]]:
    for dates in living_dates:
        dates[0] = (datetime.now() + timedelta(days=60)).strftime('%d.%m.%Y')
    # Возвращаем обновленный список с датами 
    return living_dates
    
    
def parse_special_offer_ai(text: str, today: str) -> dict:
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY")
    )

    """
    Анализирует текст спецпредложения и извлекает:
    - периоды бронирования
    - периоды проживания
    - минимальные ночи
    - формулу скидки
    """

    system_prompt = """
        Ты анализируешь текст специальных предложений отелей и извлекаешь структурированные данные.

        Правила:
        1. Используй только информацию из текста.
        2. Никогда не придумывай даты.
        3. Если указано "до DATE" или "бронирование доступно до DATE", началом периода считаем сегодняшнюю дату.
        4. Начало периода не может быть больше конца.
        5. Минимальное количество ночей должно быть числом.
        6. Если данных нет — возвращай пустой список или null.
        7. Все даты возвращай строго в формате ДД.ММ.ГГГГ.

        Верни строго JSON объект со структурой:

        {
        "booking_periods": [["ДД.ММ.ГГГГ","ДД.ММ.ГГГГ"]],
        "living_periods": [["ДД.ММ.ГГГГ","ДД.ММ.ГГГГ"]],
        "min_nights": number,
        "formula": "строка формулы"
        }

        Где:
        C — цена за ночь без скидки
        N — цена за ночь со скидкой
        Формула должна вычислять N.
        """

    user_prompt = f"""
        Сегодняшняя дата: {today}

        Текст специального предложения:

        {text}

        Извлеки данные.
        """

    try:

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )

        result = json.loads(response.choices[0].message.content)

        return result

    except Exception as e:

        print("AI parsing error:", e)

        return {
            "booking_periods": [],
            "living_periods": [],
            "min_nights": None,
            "formula": None
        }


# Функция определяющая на какие категории номеров, распространяется спец предложение
# TODO: оптимизировать функцию
def get_category(string: str) -> Union[str, List[str], None]:
    # Проверяем на наличие фразы "все категории вилл"
    if "все категории вилл" in string:
        return "Все виллы"
    # Проверяем на наличие фразы "все категории"
    elif "все категории" in string:
        return "Все категории"
    # Ищем отдельные категории
    else:
        # с помощью регулярного выражения, находим категории попадающие под шаблон (шаблон находить только первое слово после слова "категории")
        # TODO: оптимизировать поиск
        matches = re.findall(r'категории «(.*?)»', string)
        if matches:
            return matches  # Возвращаем найденные категории
        else:
            return None     # Ничего не найдено, пропускаем строку
        

# Функция определяет суммируется ли специальное предложение с программой лояльности или другими спец предложениями
# выяснилось, что с другими спецпредложениями никакая акция суммироваться не может, следовательно - нужно удалить данную проверку из функции
# TODO: оптимизировать функцию
def analyze_offers(line: str) -> Union[Tuple[bool], Tuple[None]]:
    # Инициализируем переменные "программа лояльности" и "другие спецпредложения"
    summ_loyalty = None
    
    # Определяем перемнные, списки с возможными фразами свидетельствующими о суммировании
    loyalty = 'суммируется с программой лояльности'
    not_loyalty = 'не суммируется с программой лояльности'
    
    if loyalty in line.lower() and not_loyalty not in line.lower():
        summ_loyalty = True
    elif loyalty not in line.lower() and not_loyalty in line.lower():
        summ_loyalty = False
    else:
        summ_loyalty = None
        
    return summ_loyalty


def collect_offer_data(browser):

    lines = []

    category = []
    living_dates = []
    date_before = []
    summ_with_loyalty = False

    title = browser.find_element(By.CLASS_NAME, 'f-h1')

    lines.append(title.text)

    core = browser.find_element(By.XPATH, "//div[contains(@class, 'block--content is_cascade')]/p")
    lines.append(core.text)

    wait = WebDriverWait(browser, 10)

    ul_element = wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//*[starts-with(local-name(), 'h') and contains(normalize-space(.), 'Условия')]/following::ul[1]"
    )))

    li_elements = ul_element.find_elements(By.TAG_NAME, "li")

    for li in li_elements:

        s = li.text
        lines.append(s)

        category_result = get_category(s)
        if category_result:
            category = category_result

        summ_with_loyalty_result = analyze_offers(s)
        if summ_with_loyalty_result:
            summ_with_loyalty = summ_with_loyalty_result

    offer_text = '\n'.join(lines)

    stop_phrase = ' только при обращении в единый контактный центр по номеру 8 800 550 52 71.'
    offer_text = offer_text.replace(stop_phrase, '.')

    print(f"\nТекст специального предложения:\n{offer_text}\n")

    # Получаем сегодняшнюю дату
    today = datetime.today().strftime("%d.%m.%Y")

    # AI парсинг
    ai_data = parse_special_offer_ai(offer_text, today)

    living_dates = ai_data.get("living_periods", [])
    date_before = ai_data.get("booking_periods", [])
    min_rest_days = ai_data.get("min_nights")
    formula = ai_data.get("formula")

    # Особая логика для раннего бронирования
    if title.text == 'Раннее бронирование':
        living_dates = early_booking(living_dates)

    offer = {
        "Название": title.text,
        "Категория": category,
        "Даты проживания": living_dates,
        "Даты бронирования": date_before,
        "Формула расчета": formula,
        "Минимальное количество дней": min_rest_days,
        "Суммируется с программой лояльности": summ_with_loyalty,
        "Текст предложения": offer_text
    }

    print(
        "Итог по собранным параметрам:\n"
        f"Название: {offer['Название']}\n"
        f"Категория: {offer['Категория']}\n"
        f"Период проживания: {offer['Даты проживания']}\n"
        f"Период бронирования: {offer['Даты бронирования']}\n"
        f"Формула расчета: {offer['Формула расчета']}\n"
        f"Минимальное количество дней: {offer['Минимальное количество дней']}\n"
        f"Суммируется с программой лояльности: {offer['Суммируется с программой лояльности']}\n"
    )

    return offer

    


        
