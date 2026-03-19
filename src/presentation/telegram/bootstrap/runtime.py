from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram.fsm.storage.redis import RedisStorage

from src.infrastructure.orchestration.pipeline_orchestrator import PipelineOrchestrator
from src.infrastructure.parsers.selenium_offers_parser_runner import SeleniumOffersParserRunner
from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.infrastructure.repositories.postgres_admin_events_repository import PostgresAdminEventsRepository
from src.infrastructure.repositories.postgres_admin_insights_repository import PostgresAdminInsightsRepository
from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_desired_matches_run_repository import PostgresDesiredMatchesRunRepository
from src.infrastructure.repositories.postgres_guests_repository import PostgresGuestsRepository
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository
from src.infrastructure.repositories.postgres_notifications_repository import PostgresNotificationsRepository
from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository
from src.infrastructure.synchronization.recalculation_run_coordinator import RecalculationRunCoordinator
from src.presentation.telegram.handlers.bot_handlers import TelegramBotHandlers
from src.presentation.telegram.services.notification_delivery import TelegramNotificationDelivery
from src.presentation.telegram.services.use_cases_adapter import (
    TelegramPresentationServices,
    TelegramUseCasesDependencies,
    build_telegram_presentation_services,
)
from src.presentation.telegram.settings import TelegramRuntimeSettings, load_telegram_runtime_settings
from src.presentation.telegram.state.session_store import InMemorySessionStore


@dataclass(frozen=True, slots=True)
class TelegramRuntime:
    settings: TelegramRuntimeSettings
    bot_tz: ZoneInfo | timezone
    sessions: InMemorySessionStore
    services: TelegramPresentationServices
    pipeline: PipelineOrchestrator
    handlers: TelegramBotHandlers


def build_telegram_runtime(*, settings: TelegramRuntimeSettings | None = None) -> TelegramRuntime:
    runtime_settings = settings or load_telegram_runtime_settings()
    bot_tz = _resolve_bot_timezone(runtime_settings.timezone_name)

    redis_storage = RedisStorage.from_url(runtime_settings.redis_url)
    sessions = InMemorySessionStore(storage=redis_storage)

    deps = _build_adapter_dependencies()
    services = build_telegram_presentation_services(deps=deps)
    rates_runner = SeleniumRatesParserRunner(
        rules_repo=deps.rules_repo,
        headless=runtime_settings.selenium_headless,
        wait_seconds=runtime_settings.selenium_wait_seconds,
    )
    offers_runner = SeleniumOffersParserRunner(
        rules_repo=deps.rules_repo,
        headless=runtime_settings.selenium_headless,
        wait_seconds=runtime_settings.selenium_wait_seconds,
        fail_fast=False,
    )
    pipeline = PipelineOrchestrator(
        admin=services.admin,
        system=services.system,
        notifications=services.notifications,
        notification_delivery=TelegramNotificationDelivery(),
        rates_runner=rates_runner,
        offers_runner=offers_runner,
    )
    handlers = TelegramBotHandlers(
        services=services,
        sessions=sessions,
        pipeline=pipeline,
        admin_telegram_id=runtime_settings.admin_telegram_id,
    )
    return TelegramRuntime(
        settings=runtime_settings,
        bot_tz=bot_tz,
        sessions=sessions,
        services=services,
        pipeline=pipeline,
        handlers=handlers,
    )


def _build_adapter_dependencies() -> TelegramUseCasesDependencies:
    lock_key = int(os.getenv("RECALC_ADVISORY_LOCK_KEY", "90412031"))
    return TelegramUseCasesDependencies(
        identities_repo=PostgresUserIdentitiesRepository(),
        guests_repo=PostgresGuestsRepository(),
        admin_events_repo=PostgresAdminEventsRepository(),
        admin_insights_repo=PostgresAdminInsightsRepository(),
        rates_repo=PostgresDailyRatesRepository(),
        offers_repo=PostgresOffersRepository(),
        rules_repo=PostgresRulesRepository(),
        matches_run_repo=PostgresMatchesRunRepository(),
        desired_matches_run_repo=PostgresDesiredMatchesRunRepository(),
        notifications_repo=PostgresNotificationsRepository(),
        recalculation_coordinator=RecalculationRunCoordinator(advisory_lock_key=lock_key),
    )


def _resolve_bot_timezone(timezone_name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logging.getLogger(__name__).warning(
            "timezone_not_found key=%s fallback=UTC+03:00 install=tzdata",
            timezone_name,
        )
        return timezone(timedelta(hours=3))
