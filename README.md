# guest_conditions_bot

Telegram-бот для подбора подходящих предложений по условиям гостя.

## Production Runtime

- Production entry point: `main.py`
- Docker/compose запускают именно `main.py`
- Бот стартует через современный bootstrap/runtime path в `src/presentation/telegram/bootstrap/`
- Каталог `scripts/` не участвует в production startup и нужен только для manual/admin/diagnostic задач

Запуск:

```bash
python main.py
```

## Архитектура

Проект организован по слоям:

- `src/domain`
  - бизнес-логика, value objects, pricing rules, occupancy rules
- `src/application`
  - use cases, DTO, ports
- `src/infrastructure`
  - Postgres repositories, Selenium parsers/sources, orchestration
- `src/presentation/telegram`
  - Telegram handlers, keyboards, presenters, states, isolated scenario flows
- `src/presentation/telegram/bootstrap`
  - runtime assembly, app creation, handler registration, scheduler hookup

Ключевые решения, уже зафиксированные в кодовой базе:

- production runtime отделён от вспомогательных scripts
- composition/wiring вынесены из `bot.py` и старого giant adapter
- Telegram use-case surface разрезан на узкие фасады
- pipeline orchestration вынесен из `presentation` в `infrastructure/orchestration`
- Telegram delivery отделён от системного orchestration
- `category_rules` имеют один runtime source of truth: Postgres
- Telegram сценарии развиваются как изолированные flows

## Runtime И Pipeline

Актуальный pipeline работает из bot runtime:

1. парсер цен
2. парсер офферов
3. пересчёт цен для гостей
4. anti-spam comparison и уведомления

Источники запуска:

- nightly scheduler в Telegram bootstrap
- manual triggers через Telegram admin flow

## Rates Source Rollout

Основной рекомендуемый runtime режим теперь:

- `USE_TRAVELLINE_RATES_SOURCE=true`
- `TRAVELLINE_ENABLE_PUBLISH=true`
- `TRAVELLINE_COMPARE_ONLY=false`
- `TRAVELLINE_FALLBACK_TO_SELENIUM=true`

В этом режиме:

- rates publish path идёт через Travelline
- downstream по-прежнему получает только `DailyRate`
- при ошибке Travelline publish path может явно откатиться на Selenium через fallback
- compare-only path остаётся доступным отдельно и не удалён

Обязательные Travelline env:

- `TRAVELLINE_HOTEL_CODE`
- `TRAVELLINE_BASE_URL`
- `TRAVELLINE_TIMEOUT_SECONDS`

### Режим A: Travelline publish as primary

```env
USE_TRAVELLINE_RATES_SOURCE=true
TRAVELLINE_ENABLE_PUBLISH=true
TRAVELLINE_COMPARE_ONLY=false
TRAVELLINE_FALLBACK_TO_SELENIUM=true
```

### Режим B: Selenium primary

```env
USE_TRAVELLINE_RATES_SOURCE=false
TRAVELLINE_ENABLE_PUBLISH=false
TRAVELLINE_COMPARE_ONLY=false
TRAVELLINE_FALLBACK_TO_SELENIUM=true
```

### Режим C: Shadow compare mode

```env
USE_TRAVELLINE_RATES_SOURCE=false
TRAVELLINE_ENABLE_PUBLISH=false
TRAVELLINE_COMPARE_ONLY=true
TRAVELLINE_FALLBACK_TO_SELENIUM=true
```

Откат обратно на Selenium не требует изменений кода: достаточно переключить env-флаги на режим B.

Это означает:

- `main.py` — единственный production launcher
- старый legacy-manual contour вокруг `scripts/run_pipeline.py` удалён
- duplicate launcher `scripts/run_telegram_bot.py` больше не используется и удалён
- parser/runtime path больше не зависит от `category_rules.csv`

## Manual/Admin/Diagnostic Scripts

Оставшиеся scripts в `scripts/` не являются production runtime.

### Operational/Admin-Support

- `scripts/run_selenium_offers.py`
  - ручной запуск offers parser
  - полезен для manual/admin операций и диагностики
- `scripts/get_best_period.py`
  - CLI query utility для лучшего периода по гостю и группе
- `scripts/get_period_quotes.py`
  - CLI query utility для period quotes из `matches_run`
- `scripts/link_user_identity.py`
  - ручная привязка external identity к `guest_id`
- `scripts/unlink_user_identity.py`
  - ручное удаление identity linkage

### Diagnostic Utilities

- `scripts/run_selenium_rates.py`
  - smoke/inspection utility
  - single-date, single-adult проверка текущего rates parser stack
- `scripts/run_selenium_rates_parallel.py`
  - full manual rates parser utility
  - multi-date, multi-adults прогон текущего parallel parser stack

## Что Сознательно Отложено

Это backlog архитектурных улучшений, а не скрытые проблемы runtime:

- coexistence `python-telegram-bot` и `aiogram` state stack
- возможная дальнейшая консолидация remaining manual scripts
- дальнейшая ревизия diagnostic/admin surface только по отдельным safe этапам

## Где Смотреть Дальше

- `PROJECT_CONTEXT.md`
  - более подробная operational картина
- `src/presentation/telegram/bootstrap/`
  - текущий runtime bootstrap
- `src/infrastructure/orchestration/pipeline_orchestrator.py`
  - системная orchestration-логика pipeline
