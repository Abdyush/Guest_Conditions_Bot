from datetime import datetime, timedelta
import time
from typing import Dict
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
#from parser.database.database import insert_data


        
# Функция принимающая на вход дату, словарь с найденными датами, и тип выезд/заезд и находит соответсвующую дате кнопку    
def find_date_btn(dt: datetime, dates_dict: Dict, procedure: str) -> WebElement:
    print(f"[trace] find_date_btn start dt={dt}, procedure={procedure}")
    dt = dt.strftime('%d.%m.%y')
    # Преобразование строки в объект datetime
    if procedure == 'arrival':
        date_object = datetime.strptime(dt, "%d.%m.%y")
    elif procedure == 'checkout':
        date_object = datetime.strptime(dt, "%d.%m.%y") + timedelta(days=1)
    # Извлечение номера года и месяца а также дня
    y_m = date_object.strftime("%Y-%m")  
    d = date_object.day        
    # Находим кнопку с соответсвующим числом в словаре     
    date_btn = [num for num in dates_dict[y_m] if num.text == str(d)][0]
    
    return date_btn


# Функция принимающая на вход элемент - рамку в которой содержаться кнопки с датами, и формирует словарь где ключи - месяц, а значения - список номеров дней
def find_dates(frame: WebElement) -> Dict:
    print("[trace] find_dates start")
    time.sleep(5)
    try:
        # Ждём появления нужного блока
        frame2 = frame.find_element(By.XPATH, "//div[@data-mode]")
    except TimeoutException:
        print("Не удалось найти блок с data-mode внутри переданного frame")
        raise

    months = frame2.find_elements(By.XPATH, './/div[@data-month]')
    if len(months) < 2:
        print("Найдено меньше двух месяцев в календаре — возможно, DOM изменился")
        raise Exception("Недостаточно блоков с месяцами")

    data_months = [el.get_attribute("data-month") for el in months]
    dates = {
        data_months[0][:7]: [d for d in months[0].find_elements(By.XPATH, './/span') if d.text.isdigit()],
        data_months[1][:7]: [d for d in months[1].find_elements(By.XPATH, './/span') if d.text.isdigit()],
    }

    return dates



# Функция поиска карточек с доступными категориями
def find_categories(browser):
    print("[trace] find_categories start")
    selected_buttons = []
    while True:
        # Определяем переменную start со значением - длиной списка selected_buttons (в начале он пустой)
        start = len(selected_buttons)
        # находим на всех карточках с категориями номеров, кнопки "выбрать" и формируем во временный список
        temp_list = [x for x in browser.find_elements(By.CLASS_NAME, 'tl-btn') if x.text != '']
        # добавляем временный список в список selected_buttons и формируем множество уникальных элементов
        selected_buttons = set(selected_buttons).union(set(temp_list))
        # Определяем переменную end со значением - длиной списка selected_buttons
        end = len(selected_buttons)
        # спим 3 секунды для загрузки
        # TODO: Оптимизировать ожидание
        #time.sleep(3)
        # если перемнная длина списка в начале совпала с длиной списка в конце, значит новые кнопки "выбрать" на странице закончились
        if start == end:
            # временный список становиться переменной selected_buttons (не помню почему), и цикл завершается
            selected_buttons = temp_list
            break
        # если длины разные, значит скроллим страницу до последнего элемента во временном списке и продолжаем поиск в цикле
        browser.execute_script("return arguments[0].scrollIntoView(true);", temp_list[-1])
        # спим 3 секунды для загрузки
        # TODO: Оптимизировать ожидание
        time.sleep(1)
        # Этот процесс поиска доступных кнопок, приходиться каждый раз потворять в цикле, потому что с каждым возвратом на траницу с карточками,
        # кнопки и их идентификаторы обновляются, это связано с тем, что в любой момент, определенная категория может стать недоступной для бронирования
   
    return selected_buttons 


# Функция загрузки сайта и клик по кнопке найти
def find_btn(browser):
    print("[trace] find_btn start")
    browser.get('https://mriyaresort.com/booking/')
    time.sleep(5)
    # Явное ожидание элемента .block--content
    wait = WebDriverWait(browser, 15)
    frame = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'block--content')))
    print('Нашел рамку "block--content"')
    browser.execute_script("arguments[0].scrollIntoView(true);", frame)

    try:
        el = frame.find_element(By.ID, 'tl-booking-form')
        print('Нашел рамку "tl-booking-form"')
    except NoSuchElementException:
        return

    # Ждём iframe внутри формы
    wait = WebDriverWait(el, 10)
    iframes = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, 'iframe')))

    if len(iframes) < 2:
        return

    iframe = iframes[1]
    browser.switch_to.frame(iframe)
    print('Нашел и переключился на iframe')
   
    time.sleep(3)
    # Ожидание контейнера внутри iframe
    container = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'page-container'))
    )
    print('Нашел "page-container"')
    time.sleep(3)
    
    # Поиск и клик на кнопку "Найти"
    time.sleep(3)
    buttons = container.find_elements(By.TAG_NAME, 'span')
    
    if buttons:
        find_buttons = list(filter(lambda el: el.text.strip() == "Найти", buttons))
        return find_buttons[0]
    else:
        print('Не нашел кнопку найти')
        

# Функция переключающая даты заезда и выезда
def switch_dates(browser, date):
    print(f"[trace] switch_dates start for date={date}")
    wait = WebDriverWait(browser, 15)

    input_date = browser.find_element(By.CLASS_NAME, 'x-hcp__text-field')
    print('Нашел элемент "input_date"')
    
    input_btn = input_date.find_element(By.TAG_NAME, 'input')
    print('Нашел элемент "input_btn"')
    
    browser.execute_script("arguments[0].scrollIntoView(true);", input_btn)
    print('Проскроллил к "input_btn"')
    
    #wait.until(EC.element_to_be_clickable(input_btn))
    #print('"input_btn" стала кликабельной')
    
    browser.execute_script("arguments[0].click();", input_btn)
    print('Кликнул на "input_btn"')
    
    frame1 = browser.find_element(By.CLASS_NAME, 'x-modal__container')
    print('Нашел рамку выбора дат "x-modal__container"')
    
    # В появившейся рамке, ищем список дат, на которые можно нажать
    try:
        time.sleep(3)
        dates = find_dates(frame1) 
        print('Нашел список дат для выбора')
    except:
        print('Не нашел dates, спит 3 секунды и пробует снова')
        time.sleep(3)
        dates = find_dates(frame1)
        print('Нашел список дат для выбора со второй попытки')
    
     
    # Выбираем среди списка и нажимаем кнопку заезда    
    try:
        time.sleep(5)
        arrival_btn = find_date_btn(date, dates, 'arrival')
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", arrival_btn)
        time.sleep(1)  # небольшая задержка на прогрузку анимаций
        try:
            wait.until(EC.element_to_be_clickable(arrival_btn)).click()
        except:
            browser.execute_script("arguments[0].click();", arrival_btn)
        print('Кликнул по кнопке заезда')
            
    except Exception:
        print('Кнопка заезда не найдена с первого раза, повторяет попытку')
        dates = find_dates(frame1)
        arrival_btn = find_date_btn(date, dates, 'arrival')
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", arrival_btn)
        time.sleep(1)  # небольшая задержка на прогрузку анимаций
        try:
            wait.until(EC.element_to_be_clickable(arrival_btn)).click()
        except:
            browser.execute_script("arguments[0].click();", arrival_btn)
        print('Кликнул по кнопке заезда, со второй попытки')
        
    # Выбираем среди списка и нажимаем кнопку выезда 
    try:
        checkout_btn = find_date_btn(date, dates, 'checkout')
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkout_btn)
        time.sleep(1)  # небольшая задержка на прогрузку анимаций
        try:
            wait.until(EC.element_to_be_clickable(checkout_btn)).click()
        except:
            browser.execute_script("arguments[0].click();", checkout_btn)
        print('Кликнул по кнопке выезда')
            
    except Exception:
        print('Кнопка заезда не найдена с первого раза, повторяет попытку')
        dates = find_dates(frame1)
        checkout_btn = find_date_btn(date, dates, 'checkout')
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkout_btn)
        time.sleep(1)  # небольшая задержка на прогрузку анимаций
        try:
            wait.until(EC.element_to_be_clickable(checkout_btn)).click()
        except:
            browser.execute_script("arguments[0].click();", checkout_btn)
        print('Кликнул по кнопке выезда, со второй попытки')


# Функция проверяющая, остался ли у данной категории последний номер
def check_last_room(category):
    print("[trace] check_last_room start")
    last_room = None
    try:
        parent_div = category.find_element(By.XPATH, './/ancestor::div[@data-shift-animate="true"]')
        child_div = parent_div.find_element(By.XPATH, './/div[contains(text(), "Остался") and contains(text(), "номер")]')        
        last_room = True
    
    except:
        last_room = False
        
    return last_room

# Функция собирающая все данные со страницы коитегории и добавляющая их в базу
def collect_category_data(browser, last_room, conn, date):
    print(f"[trace] collect_category_data start for date={date}")
    # достаем название категории посредством поиска всех элемнтов с тегом div и атрибутом tl-id="plate-title" и выбираем первый из них,
    # этот элемент скорее всего является названием категории (способ не надежный)
    # TODO: Оптимизировать поиск
    try:
        name = [x.text for x in browser.find_elements(By.CSS_SELECTOR, 'div[tl-id="plate-title"]') if x.text  != ''][0]
        print(f'Получил название категории: {name}')
    except:
        print(f'Не удалось найти название категории')
        
    # достаем цены, находя с помощью css селектора все элементы span с классом numeric, удаляем лишнее форматирование и преобзауем в числа
    prices = [int(x.text.replace('\u2009', '')) for x in browser.find_elements(By.CSS_SELECTOR, 'span[class="numeric"]') if x.text  != '']
    if len(prices) < 2:
        print(f'{name} в списке с предполагаемыми данными находиться меньше двух элементов')
          
    # первые два элемента этого списка будут стоимости без скидок по специальным предложениям, по тарифам "только завтраки" и "полный пансион"
    # способ поиска можно сделать вернее, если найти также названия тарифов
    # TODO: Оптимизировать поиск
    only_breakfast = prices[0]
    full_pansion = prices[1]
    print(f'Цены: Завтрак — {only_breakfast}, Полный пансион — {full_pansion}')
    
    # Формируем словарь с ценами без скидок 
    date_dict = {'только завтраки': only_breakfast,
                'полный пансион': full_pansion}
    

    for tariff, price in date_dict.items():
        try:
            insert_data(conn, name, date, tariff, price, last_room)
            
        except Exception as e:
            print(f"Ошибка вставки в БД: {e}")
            
    conn.commit()
    
    # Находим кнопку возврата к выбору карточек кликаем по ней и ожидаем 3 секунды для загрузки
    back = browser.find_element(By.CLASS_NAME, 'x-hnp__link')
    WebDriverWait(browser, 10).until(EC.element_to_be_clickable(back))
    browser.execute_script("arguments[0].click();", back)
    print(f'Нашел кнопку возврата к выбору категорий и кликнул по ней, спим 3 секунды')
    # TODO: Оптимизировать ожидание
    time.sleep(3)
