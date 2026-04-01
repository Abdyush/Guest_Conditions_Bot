# guest_conditions_bot — Project Context

## 1) Назначение проекта

`guest_conditions_bot` — Telegram-бот для подбора гостиничных предложений под профиль гостя:
- хранит профиль гостя и его ограничения по цене/размещению
- собирает daily rates и special offers через Selenium
- рассчитывает подходящие варианты на горизонте дат
- показывает доступные категории/лучшие периоды/квоты в Telegram
- отправляет проактивные уведомления по новым или снова релевантным предложениям

Проект ориентирован на production runtime через Telegram-бота. Каталог `scripts/` используется как вспомогательный CLI-контур для ручных операций, диагностики и запросов к данным.

## 2) Архитектура

Проект организован по слоям:
- `src/domain` — сущности (`Offer`, `Quote`, `GuestPreferences`, `DailyRate`), value objects (`Money`, `Discount`, `DateRange`, `BankStatus`, `LoyaltyStatus`, `CategoryRule`) и доменные сервисы (`PricingService`, `DatePriceSelector`, `PeriodBuilder`, capacity/child policies)
- `src/application` — DTO, порты и use cases
- `src/infrastructure` — Postgres repositories, Selenium gateways/parsers, orchestration, synchronization
- `src/presentation/telegram` — Telegram handlers, сценарии, presenters, keyboards, navigation, state
- `src/presentation/telegram/bootstrap` — сборка runtime, регистрация handlers, scheduler/fallback jobs

Основной стиль архитектуры — clean/layered, но кодовая база уже содержит прагматичные runtime-адаптеры и фасады, а не только “чистые” use case boundaries.

## 3) Production runtime

Основной entry point:
- `main.py`

Runtime path:
- `main.py` поднимает `.env` и импортирует `src.presentation.telegram.bot.run_polling`
- `src/presentation/telegram/bot.py` строит PTB `Application`
- `src/presentation/telegram/bootstrap/runtime.py` собирает runtime dependencies
- `src/presentation/telegram/bootstrap/application.py` регистрирует handlers, error handler, scheduler и фоновые задачи

Production runtime использует:
- `python-telegram-bot` как bot runtime / update processing / job queue
- `aiogram` Redis FSM storage как backend для состояния сессий
- PostgreSQL как основное долговременное хранилище
- Redis как хранилище FSM state/data
- Selenium для загрузки тарифов и офферов

Важно:
- `scripts/` не являются production startup surface
- Docker/compose запускают именно runtime бота, а не отдельный parser-only entry point

## 4) Telegram runtime и state

Текущий runtime собирается в `build_telegram_runtime()` и включает:
- runtime settings из env
- `RedisStorage` для FSM state/data
- `InMemorySessionStore` как кеш + adapter над Redis-backed FSM storage
- фасады presentation services (`identity`, `profile`, `available_offers`, `best_periods`, `period_quotes`, `notifications`, `admin`, `system`)
- `PipelineOrchestrator`
- `TelegramBotHandlers`

Сценарии Telegram, явно зарегистрированные в коде:
- onboarding
- registration
- available offers
- best periods
- period quotes
- notification offers
- admin menu
- admin commands

Текущее состояние сессии живёт в двух слоях:
- оперативный in-process cache в `InMemorySessionStore`
- persisted FSM data в Redis через `aiogram.fsm.storage.redis.RedisStorage`

Это значит, что старое представление “сессии только в памяти” уже неактуально.

## 5) Планировщик и фоновые задачи

В `src/presentation/telegram/bootstrap/application.py` бот поднимает:
- flush loop для периодической записи session cache в Redis
- daily job `nightly_pipeline` в `03:00` по `BOT_TIMEZONE`
- daily job `midday_notifications` в `12:00` по `BOT_TIMEZONE`

Если PTB job queue недоступен, включается fallback на `asyncio`-циклы с теми же расписаниями.

Назначение задач:
- `nightly_pipeline` запускает rates parser -> offers parser -> recalculation без отправки уведомлений
- `midday_notifications` запускает только фазу уведомлений по последнему доступному run

## 6) Pipeline orchestration

Координация пайплайна живёт в `src/infrastructure/orchestration/pipeline_orchestrator.py`.

Поддерживаются операции:
- `run_daily_pipeline()`
- `run_notifications_only()`
- `run_categories_parser()`
- `run_offers_parser()`
- `run_recalculation()`

Свойства текущей orchestration-логики:
- внутри процесса есть `asyncio.Lock`, предотвращающий параллельный запуск двух pipeline-задач
- при занятом lock операция не стартует и логируется как `busy`
- orchestration пишет admin events по каждому шагу: parsers, recalculation, notifications, pipeline
- notifications отправляются отдельным delivery-слоем, а после успешной доставки строки помечаются sent в repository

## 7) Recalculation и данные прогонов

Основной пересчёт вызывается через `TelegramSystemFacade._recalculate_matches()`:
- собирает rates, offers, guests, rules
- строит `PricingService`, `DatePriceSelector`, `CalculateMatchesForAllGuests`
- формирует `MatchedDateRecord` для всех результатов
- отдельно отбирает записи, которые проходят порог `desired_price_per_night`

Результаты пишутся в две таблицы-ленты:
- `matches_run` — все найденные совпадения
- `desired_matches_run` — только записи, прошедшие по целевой цене гостя

Текущее поведение хранения:
- старые строки не `TRUNCATE`-ятся
- каждый новый `run_id` публикуется как `snapshot_id`
- активный snapshot хранится в таблице `active_snapshots`
- методы `get_latest_run_id()` сначала читают активный snapshot, а затем fallback-ятся на самый свежий `computed_at`

Следствие: старое описание “таблица текущего прогона = TRUNCATE + INSERT” больше не соответствует коду.

## 8) Уведомления и anti-spam

Подготовка уведомлений идёт через `PrepareGuestNotificationBatches`, а фактическая доставка — через `TelegramNotificationDelivery`.

Anti-spam реализован в `PostgresNotificationsRepository` не как простой уникальный ключ на дневную строку, а как более сложная схема:
- записи сначала агрегируются в интервалы (`period_label`)
- historical rows нормализуются относительно `as_of_date`
- сравнение делается по логическому ключу `(guest_id, category_name, group_id, tariff)`
- новое уведомление допускается, если:
  - для ключа ещё не было уведомлений
  - текущая лучшая цена стала ниже последней уведомлённой
  - или истёк cooldown (`PROACTIVE_NOTIFICATION_COOLDOWN_DAYS`)

В таблице `notifications` хранится история уже отправленных уведомлений, включая:
- `availability_period`
- `period_label`
- цены до/после
- offer / loyalty / bank признаки
- `computed_at`
- `notified_at`

Уникальный индекс существует, но он служит частью дедупликации при записи агрегированных notification rows, а не описывает всю anti-spam-логику сам по себе.

## 9) Бизнес-правила ценообразования

Ключевой доменный сервис: `src/domain/services/pricing_service.py`.

Текущее поведение:
- базовая цена берётся из daily rate
- для `PER_ADULT` групп может добавляться детская доплата по `ChildSupplementPolicy`
- оффер применяется к периоду, если `Offer.is_applicable(...)` возвращает `True`
- loyalty применяется только если нет bank discount и если оффер совместим с loyalty
- bank discount имеет приоритет над loyalty

Bank policy по умолчанию:
- `SBER_PREMIER`: 20% без оффера, 10% после оффера
- `SBER_FIRST`: 25% без оффера, 15% после оффера
- `SBER_PRIVATE`: 30% без оффера, 15% после оффера

Loyalty policy в Telegram runtime:
- `white` 5%
- `bronze` 7%
- `silver` 8%
- `gold` 10%
- `platinum` 12%
- `diamond` 15%

Offer считается применимым только если одновременно совпадают:
- `booking_date` внутри `booking_period`
- даты проживания входят в допустимые `stay_periods`
- соблюдён `min_nights`
- совпадает таргетинг по группе/категории/тарифу

## 10) Occupancy и guest profile

Профиль гостя хранит:
- `desired_price_per_night`
- `allowed_groups`
- `occupancy` (`adults`, `children_4_13`, `infants`)
- `loyalty_status` или `bank_status`
- имя и телефон

Фактические ограничения:
- ставка подбирается по `adults_count`, равному числу взрослых гостя
- доступность категорий зависит от group rules и occupancy
- `children_4_13` участвуют в расчёте доплат
- `infants_0_3` учитываются через `free_infants`/capacity rules
- если задан `bank_status`, loyalty отключается

Регистрация и обновление профиля сейчас триггерят пересчёт через `TelegramProfileFacade`.

## 11) Основные use cases и фасады

Системно значимые use cases:
- `CalculateMatchesForAllGuests`
- `GetBestPeriodsForGuestInGroup`
- `GetPeriodQuotesFromMatchesRun`
- `PrepareGuestNotificationBatches`
- `GetAdminReports`
- `GetAdminStatistics`
- `find_best_period_for_category`
- `find_group_categories_for_guest`

Telegram слой не обращается напрямую к use cases из handlers повсюду; вместо этого основная интеграция идёт через фасады в `src/presentation/telegram/services/use_cases_adapter.py`.

Это важный факт для дальнейших изменений: presentation contract проекта сегодня проходит через фасады, а не через единый “bot adapter”.

## 12) Репозитории и runtime sources of truth

Runtime repositories:
- `PostgresDailyRatesRepository`
- `PostgresOffersRepository`
- `PostgresRulesRepository`
- `PostgresGuestsRepository`
- `PostgresUserIdentitiesRepository`
- `PostgresMatchesRunRepository`
- `PostgresDesiredMatchesRunRepository`
- `PostgresNotificationsRepository`
- `PostgresAdminEventsRepository`
- `PostgresAdminInsightsRepository`

Основные runtime datasets:
- `daily_rates`
- `special_offers`
- `category_rules`
- `guest_details`
- `matches_run`
- `desired_matches_run`
- `notifications`
- `active_snapshots`
- admin tables для events/insights

`category_rules.csv` больше не является production source of truth. Runtime получает правила из Postgres repository.

## 13) Manual/admin/diagnostic scripts

Актуальные скрипты в `scripts/`:
- `run_selenium_rates.py` — smoke/inspection utility для rates parser
- `run_selenium_rates_parallel.py` — ручной multi-date/multi-adults прогон rates parser
- `run_selenium_offers.py` — ручной запуск offers parser
- `get_best_period.py` — CLI-запрос лучших периодов по `guest_id` и `group_id`
- `get_period_quotes.py` — CLI-запрос period quotes из `matches_run`
- `link_user_identity.py` — ручная привязка external identity к `guest_id`
- `unlink_user_identity.py` — ручное удаление identity linkage

Эти скрипты полезны для эксплуатации и диагностики, но не определяют production runtime architecture.

## 14) Окружение и конфигурация

Ключевые env-переменные, подтверждённые кодом:
- `TELEGRAM_BOT_TOKEN`
- `ADMIN_TELEGRAM_ID`
- `DATABASE_URL`
- `REDIS_URL`
- `BOT_TIMEZONE`
- `SELENIUM_VISIBLE`
- `SELENIUM_WAIT_SECONDS`
- `PROACTIVE_NOTIFICATION_COOLDOWN_DAYS`
- `MATCHES_LOOKAHEAD_DAYS`
- `RATES_PARSER_BATCH_PAUSE_SECONDS`
- `RATES_PARSER_RETRY_COUNT`
- `RATES_PARSER_RETRY_PAUSE_SECONDS`
- `RECALC_ADVISORY_LOCK_KEY`

Docker Compose поднимает:
- bot
- postgres
- redis

`REDIS_URL` обязателен для текущего runtime: без него `load_telegram_runtime_settings()` выбрасывает ошибку.

## 15) Конкурентность и синхронизация

Помимо process-local `asyncio.Lock` в orchestration, проект использует `RecalculationRunCoordinator`:
- сериализует recalculation внутри процесса
- коалесцирует конкурирующие trigger-ы в trailing run
- может использовать PostgreSQL advisory lock для защиты от multi-process overlap

Это важнее, чем старое предположение о “простом sequential run”: в коде уже есть отдельная синхронизация пересчёта.

## 16) Тестовое покрытие и текущее состояние

В проекте есть unit/integration-like tests для:
- domain value objects и pricing logic
- use cases
- repositories
- Selenium transforms/runners
- Telegram session/presentation helpers

Фактическое состояние по результату запуска `.\.venv\Scripts\python.exe -m pytest -q`:
- `106 passed`
- `9 skipped`
- `3 failed`

Падающие тесты:
- `tests/presentation/test_session_store.py::test_session_store_state_transitions` — тест ожидает старый API `InMemorySessionStore()` без обязательного `storage`
- `tests/test_find_best_dates_for_guest.py::test_find_best_dates_for_guest_end_to_end`
- `tests/test_find_best_dates_for_guest.py::test_two_categories_same_group_both_present_in_result_when_price_matches`

Следствие:
- тестовый набор не полностью green
- минимум часть тестов отстаёт от текущей реализации
- перед крупным рефакторингом нужно считать тестовый baseline “частично сломанным”, а не просто “непроверенным”

## 17) Практические выводы для следующего разработчика

Если вносить изменения в проект, исходить нужно из следующих фактов:
- единственный production launcher — `main.py`
- Telegram runtime = PTB + aiogram Redis FSM storage
- Redis уже является обязательной runtime-зависимостью
- pipeline split-нут на nightly recalculation и отдельный notifications job
- `matches_run` / `desired_matches_run` работают через snapshot model, а не через truncate model
- anti-spam уведомлений основан на агрегированных периодах, cooldown и сравнении лучшей цены
- presentation слой завязан на фасады `use_cases_adapter.py`
- category rules в runtime читаются из Postgres, а не из CSV

## 18) Что в проекте всё ещё выглядит переходным

Текущая кодовая база всё ещё несёт признаки эволюционного перехода:
- coexistence `python-telegram-bot` и `aiogram` не унифицирован в один стек
- `InMemorySessionStore` по имени уже не соответствует своей фактической Redis-backed роли
- часть тестов и часть документации ранее отставали от текущего runtime
- manual/admin surface остаётся разнесённым по нескольким script entry points

Это не блокирует runtime, но важно как контекст для дальнейшей стабилизации проекта.
