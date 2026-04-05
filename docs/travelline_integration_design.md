Проект уже хорошо изолирует downstream от Selenium: все расчёты работают через snapshot `daily_rates` и доменную модель `DailyRate`.

Главная проблема:
- текущий rates ingestion жёстко завязан на Selenium
- порт `DailyRatesSourcePort` декларативно есть, но фактически не используется

Вывод:
Travelline можно внедрить как **полную замену Selenium**, но только через **инфраструктурный адаптер**, а не напрямую.

---

## Архитектурный принцип

Travelline должен жить строго в `infrastructure` и не проникать в:

- domain
- application
- presentation

Целевая цепочка:


Travelline API
->
client / gateway
->
raw DTO
->
intermediate TL model
->
DailyRateInput
->
DailyRate
->
PostgresDailyRatesRepository
->
existing pipeline (pricing / matches / notifications)


---

## Что НЕ менять (на первом этапе)

- domain entities
- pricing logic
- period builder
- match calculation
- desired matches
- notifications
- telegram presenters
- snapshot semantics
- Selenium parser

---

## Стратегия внедрения

### Phase 1 — Compare mode

- Travelline работает параллельно Selenium
- данные НЕ публикуются в `daily_rates`
- сохраняется compare-результат

### Phase 2 — Feature flag

- включается publish через флаг
- Selenium остаётся fallback

### Phase 3 — Replacement

- Travelline становится основным источником

---

## Структура файлов

### Новые файлы


src/infrastructure/travelline/client.py
src/infrastructure/travelline/contracts.py
src/infrastructure/travelline/availability_gateway.py
src/infrastructure/travelline/hotel_info_gateway.py
src/infrastructure/travelline/models.py
src/infrastructure/travelline/rates_transform.py
src/infrastructure/sources/travelline_rates_source.py
src/infrastructure/parsers/travelline_rates_parser_runner.py

scripts/compare_selenium_vs_travelline_rates.py

tests/infrastructure/test_travelline_client.py
tests/infrastructure/test_travelline_rates_transform.py
tests/infrastructure/test_travelline_rates_parser_runner.py


---

## Модели

### TravellineRoomTypeInfo

```python
@dataclass
class TravellineRoomTypeInfo:
    code: str
    name: str | None
    kind: str | None
    max_adult_occupancy: int | None
    max_occupancy: int | None
TravellineAvailabilityQuote
@dataclass
class TravellineAvailabilityQuote:
    hotel_code: str
    check_in: str
    check_out: str
    adults: int

    room_type_code: str
    room_type_name: str | None

    rate_plan_code: str
    service_rph: str | None

    price_before_tax: float | None
    price_after_tax: float | None
    currency: str | None

    free_cancellation: bool | None
Основные компоненты
TravellineClient
class TravellineClient:
    def get_hotel_info(self, hotel_code: str) -> dict: ...
    def get_availability(self, hotel_code: str, check_in: str, check_out: str, adults: int) -> 
    dict: ...

TravellineAvailabilityGateway
class TravellineAvailabilityGateway:
    def fetch_one_night_quotes(...): ...
    
TravellineHotelInfoGateway
class TravellineHotelInfoGateway:
    def fetch_room_type_map(...): ...
rates_transform.py

Функции:

def map_raw_to_quotes(...): ...
def deduplicate_quotes(...): ...
def assign_meal_plans(...): ...
def map_to_daily_rate_inputs(...): ...
TravellineRatesSource
class TravellineRatesSource:
    def get_daily_rates(...): ...
TravellineRatesParserRunner
class TravellineRatesParserRunner:
    def run_compare_only(self): ...
    def run_and_publish(self): ...
Mapping правила
One-night contract

Используем только:

check_in = D
check_out = D + 1
Цена

Используем:

price_after_tax
Категории
room_type_code -> room_type_name -> category_rules

Если нет совпадения:

логируем mismatch
Тарифы

Внутри группы:

(room_type_code, adults, date)

правило:

min(price) = "Только завтраки"
max(price) = "Полный пансион"
is_last_room

Travelline не даёт → ставим:

False
Compare mode

Сравнение по ключу:

date
adults
category_id
group_id
tariff

Метрики:

missing rows
price diff
category mismatches
tariff pairing errors
Feature flags
USE_TRAVELLINE = False
TRAVELLINE_COMPARE_ONLY = True
TRAVELLINE_PUBLISH = False
Порядок реализации
client
gateways
models
transform
runner (compare mode)
compare script
тесты
publish mode
switch
Тесты
Unit
client
transform
tariff mapping
category mapping
Integration
реальные TL данные
сравнение с Selenium
Non-goals (v1)
не трогаем downstream
не удаляем Selenium
не меняем Telegram UI
не усложняем тарифы
Status
 Design prepared
 Travelline client implemented
 Transform layer implemented
 Compare mode implemented
 Validation completed
 Production switch