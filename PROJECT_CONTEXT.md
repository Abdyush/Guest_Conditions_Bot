# guest_conditions_bot — Project Context

## 1) Архитектура

Проект использует Clean Architecture:
- `domain` — бизнес-логика и value objects (`Money`, `Offer`, `Discount`, `PricingService`, bank/loyalty, occupancy и т.д.)
- `application` — use cases, DTO, ports
- `infrastructure` — реализации портов, Postgres repositories, Selenium stack, orchestration
- `presentation/telegram` — Telegram handlers, presenters, keyboards, state, isolated flows
- `presentation/telegram/bootstrap` — runtime assembly, app creation, scheduler hookup

БД: PostgreSQL  
Доступ: SQLAlchemy 2.0 (sync)

## 2) Текущий runtime-поток (`main.py`)

Production runtime запускает Telegram-бота через `main.py`.
Каталог `scripts/` не используется как production startup surface и предназначен только для ручных operational/admin/diagnostic задач.

Дальше pipeline работает из bot runtime:
- nightly scheduler в Telegram bootstrap
- manual system/admin triggers из Telegram admin flow

Актуальный pipeline:

1. **Парсер цен**
   - запускается через `SeleniumRatesParserRunner`
   - сохраняет данные в `daily_rates`

2. **Парсер офферов**
   - запускается через `SeleniumOffersParserRunner`
   - сохраняет данные в `special_offers`

3. **Пересчёт**
   - use case читает rates/offers/guests/rules из Postgres repositories
   - сохраняет результат текущего прогона в `matches_run` и `desired_matches_run`

4. **Уведомления**
   - антиспам: сравнение с `notifications`
   - отправляются только новые предложения
   - после успешной доставки новые ключи записываются в `notifications`

Category rules:

- runtime/use cases читают `category_rules` из Postgres
- parser mapping тоже использует `category_rules` из Postgres
- CSV больше не участвует в production runtime path и может использоваться только как отдельный import artifact

Runtime wiring:

- `main.py` — production launcher
- `src/presentation/telegram/bot.py` — тонкий entry point
- `src/presentation/telegram/bootstrap/runtime.py` — dependency assembly
- `src/presentation/telegram/bootstrap/application.py` — PTB app bootstrap и scheduler hookup
- `src/infrastructure/orchestration/pipeline_orchestrator.py` — orchestration pipeline

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

Замечание: persistence и отправка уведомлений находятся в orchestration/runtime слое, а не внутри use case.

### `FindBestPeriodsInGroup`
- ищет минимальную цену по округлению до рубля
- объединяет подряд идущие даты по `(category_name, tariff_code)`
- сортирует периоды: `nights desc`, затем `price asc`, затем `start_date asc`
- возвращает `top_k`

## 6) Таблицы Postgres (актуально)

### Входные/справочные runtime-данные
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

- production runtime: `main.py`
- ручные parser/query utilities находятся в `scripts/`
- duplicate launcher `scripts/run_telegram_bot.py` удалён и больше не считается допустимым способом запуска runtime

Оставшиеся manual/admin/diagnostic scripts:

- `scripts/run_selenium_rates.py`
  - smoke/inspection utility для одного stay date и одного adults count
- `scripts/run_selenium_rates_parallel.py`
  - full manual rates parser utility для диапазона дат и нескольких adults counts
- `scripts/run_selenium_offers.py`
  - ручной запуск offers parser
- `scripts/get_best_period.py`
  - support/query utility для лучшего периода
- `scripts/get_period_quotes.py`
  - support/query utility для quotes из `matches_run`
- `scripts/link_user_identity.py`
  - ручная привязка external identity к `guest_id`
- `scripts/unlink_user_identity.py`
  - ручное удаление identity linkage

## 8) Требования окружения

- `DATABASE_URL` в `.env` (формат `postgresql+psycopg2://...`)
- установлены зависимости `sqlalchemy`, `psycopg2-binary`, `python-dotenv`
- запуск production runtime: `python main.py`

## 9) Принятые Архитектурные Решения

- giant Telegram adapter больше не используется как единый business gateway
- composition/wiring вынесены из `bot.py` и старого adapter surface
- pipeline orchestration вынесен из `presentation` в `infrastructure/orchestration`
- Telegram delivery отделён от orchestration
- legacy-manual contour вокруг `scripts/run_pipeline.py` удалён
- rates parser CLI surface сохранена в двух ролях:
  - smoke tool
  - full manual parser tool

## 10) Отложенные Темы

- coexistence `python-telegram-bot` и `aiogram` state stack пока не унифицирован
- remaining manual/admin scripts пока не консолидировались дальше без отдельного safe этапа
