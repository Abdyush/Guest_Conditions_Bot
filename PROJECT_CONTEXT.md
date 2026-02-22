# guest_conditions_bot — Project Context

## 1) Архитектура

Проект использует Clean Architecture:
- `domain` — бизнес-логика и value objects (`Money`, `Offer`, `Discount`, `PricingService`, bank/loyalty, occupancy и т.д.)
- `application` — use cases, DTO, ports
- `infrastructure` — реализации портов (CSV, PostgreSQL, notifier)

БД: PostgreSQL  
Доступ: SQLAlchemy 2.0 (sync)

## 2) Текущий runtime-поток (`scripts/run_pipeline.py`)

Pipeline выполняет 2 фазы:

1. **Sync CSV -> Postgres** (перезапись справочников/снимков)
   - `data/daily_rates.csv` -> `daily_rates` (TRUNCATE + INSERT)
   - `data/special_offers.csv` -> `special_offers` (TRUNCATE + INSERT)
   - `data/guest_details.csv` -> `guest_details` (TRUNCATE + INSERT)
   - `data/category_rules.csv` -> `category_rules` (TRUNCATE + INSERT)

2. **Расчёт и уведомления из Postgres-данных**
   - use case читает rates/offers/guests/rules **только из Postgres repositories**
   - сохраняет результат текущего прогона в `matches_run` (TRUNCATE + INSERT, с `run_id`)
   - антиспам: сравнение с `notifications`, отправка только новых строк
   - после отправки новые ключи записываются в `notifications`

Важно: CSV больше не участвуют в расчёте напрямую после загрузки в БД.

## 3) Бизнес-правила ценообразования

Порядок применения:
- базовая цена (`old_price`)
- оффер (если применим)
- если есть `bank_status` -> применяется bank discount, loyalty отключается
- если `bank_status` нет -> применяется loyalty (только если оффер совместим)

Bank policy:
- `SBER_PREMIER`: open 20%, after_offer 10%
- `SBER_FIRST`: open 25%, after_offer 15%
- `SBER_PRIVATE`: open 30%, after_offer 15%

Offer применим при выполнении всех условий:
- `booking_date` в `booking_period`
- дата проживания в `stay_periods`
- длина доступного непрерывного периода >= `min_nights`
- таргетинг оффера по группе/категории совпадает

## 4) Occupancy правила

- `adults_count` берётся из daily rate
- подростки 4-13 учитываются как `children_4_13` (доплата по `category_rules`)
- младенцы 0-3 ограничены `free_infants`
- bank/loyalty не меняют валидацию вместимости, только цену

## 5) Use cases

### `CalculateMatchesForAllGuests`
Отвечает за расчёт для всех гостей:
- получает ставки, офферы, гостей, правила
- строит кандидаты лучших цен по датам
- фильтрует по порогу `desired_price_per_night`
- возвращает `GuestResult` (`matched_lines`, `best_periods`)

Замечание: persistence и отправка уведомлений находятся в pipeline-скрипте, а не внутри use case.

### `FindBestPeriodsInGroup`
- ищет минимальную цену по округлению до рубля
- объединяет подряд идущие даты по `(category_name, tariff_code)`
- сортирует периоды: `nights desc`, затем `price asc`, затем `start_date asc`
- возвращает `top_k`

## 6) Таблицы Postgres (актуально)

### Входные/справочные (перезаписываются каждый запуск)
- `daily_rates`
- `special_offers`
- `guest_details`
- `category_rules`

### Результаты и антиспам
- `matches_run` — снимок результатов текущего прогона (TRUNCATE + INSERT)
- `notifications` — история отправленных уведомлений (не очищается)

Уникальный ключ антиспама в `notifications`:
`(guest_id, date, category_name, tariff, new_price_minor, offer_id, bank_status, loyalty_status)`

Если меняется `new_price_minor` (или другой компонент ключа), запись считается новой и может быть отправлена снова.

## 7) Основные файлы запуска

- основной сценарий: `scripts/run_pipeline.py`
- `scripts/run_fake.py` и `scripts/run_sample_case.py` не требуются для production pipeline (могут использоваться как demo/debug)

## 8) Требования окружения

- `DATABASE_URL` в `.env` (формат `postgresql+psycopg2://...`)
- установлены зависимости `sqlalchemy`, `psycopg2-binary`, `python-dotenv`
- запуск: `python scripts/run_pipeline.py --date-from YYYY-MM-DD --date-to YYYY-MM-DD`
