from selenium import webdriver
from datetime import datetime


# Настройка опций для Chrome
def create_browser_options():
    print("[trace] create_browser_options start")
    options = webdriver.ChromeOptions()

    # --- Headless режим ---
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-default-apps")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--mute-audio")

    # --- Логи/сертификаты ---
    options.add_argument("--log-level=3")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-insecure-localhost")

    return options


# Получение всех атрибутов элемента (через JS)
def get_attributes(driver, element) -> dict:
    return driver.execute_script(
        """
        let attr = arguments[0].attributes;
        let items = {};
        for (let i = 0; i < attr.length; i++) {
            items[attr[i].name] = attr[i].value;
        }
        return items;
        """,
        element,
    )


# Разбор даты, поддержка формулировок "сегодняшняя дата"
def parse_date(date_str):
    """Парсит дату формата DD.MM.YYYY, а также 'сегодняшняя дата'."""
    print(f"[trace] parse_date start date_str={date_str}")
    normalized = str(date_str).strip().lower()

    if normalized in ("сегодняшняя дата", "сегодня", "today"):
        return datetime.today().date()

    return datetime.strptime(normalized, "%d.%m.%Y").date()
