from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram.fsm.storage.redis import RedisStorage

from src.infrastructure.orchestration.pipeline_orchestrator import PipelineOrchestrator
from src.infrastructure.parsers.feature_flagged_rates_runner import FeatureFlaggedRatesRunner
from src.infrastructure.parsers.selenium_offers_parser_runner import SeleniumOffersParserRunner
from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.infrastructure.parsers.travelline_rates_parser_runner import TravellineRatesParserRunner
from src.infrastructure.repositories.postgres_admin_events_repository import PostgresAdminEventsRepository
from src.infrastructure.repositories.postgres_admin_insights_repository import PostgresAdminInsightsRepository
from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_desired_matches_run_repository import PostgresDesiredMatchesRunRepository
from src.infrastructure.repositories.postgres_guests_repository import PostgresGuestsRepository
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository
from src.infrastructure.repositories.postgres_notifications_repository import PostgresNotificationsRepository
from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
from src.infrastructure.repositories.postgres_travelline_publish_report_repository import (
    PostgresTravellinePublishReportRepository,
)
from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository
from src.infrastructure.sources.travelline_rates_source import TravellineRatesSource
from src.infrastructure.synchronization.recalculation_run_coordinator import RecalculationRunCoordinator
from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
from src.infrastructure.travelline.client import TravellineClient
from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway
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
    logger = logging.getLogger(__name__)
    bot_tz = _resolve_bot_timezone(runtime_settings.timezone_name)

    redis_storage = RedisStorage.from_url(runtime_settings.redis_url)
    sessions = InMemorySessionStore(storage=redis_storage)

    deps = _build_adapter_dependencies(runtime_settings=runtime_settings)
    services = build_telegram_presentation_services(deps=deps)
    selenium_rates_runner = SeleniumRatesParserRunner(
        rules_repo=deps.rules_repo,
        headless=runtime_settings.selenium_headless,
        wait_seconds=runtime_settings.selenium_wait_seconds,
        batch_pause_seconds=runtime_settings.rates_parser_batch_pause_seconds,
        retry_count=runtime_settings.rates_parser_retry_count,
        retry_pause_seconds=runtime_settings.rates_parser_retry_pause_seconds,
    )
    travelline_rates_runner = _build_travelline_rates_runner(runtime_settings=runtime_settings, deps=deps)
    rates_runner = FeatureFlaggedRatesRunner(
        selenium_runner=selenium_rates_runner,
        travelline_runner=travelline_rates_runner,
        use_travelline_rates_source=runtime_settings.use_travelline_rates_source,
        travelline_compare_only=runtime_settings.travelline_compare_only,
        travelline_enable_publish=runtime_settings.travelline_enable_publish,
        travelline_fallback_to_selenium=runtime_settings.travelline_fallback_to_selenium,
    )
    logger.info(
        "rates_rollout_config use_travelline_rates_source=%s travelline_compare_only=%s "
        "travelline_enable_publish=%s travelline_fallback_to_selenium=%s",
        runtime_settings.use_travelline_rates_source,
        runtime_settings.travelline_compare_only,
        runtime_settings.travelline_enable_publish,
        runtime_settings.travelline_fallback_to_selenium,
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
        latest_runs=deps.desired_matches_run_repo,
        notification_delivery=TelegramNotificationDelivery(),
        rates_runner=rates_runner,
        offers_runner=offers_runner,
        matches_lookahead_days=runtime_settings.matches_lookahead_days,
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


def _build_adapter_dependencies(*, runtime_settings: TelegramRuntimeSettings) -> TelegramUseCasesDependencies:
    lock_key = int(os.getenv("RECALC_ADVISORY_LOCK_KEY", "90412031"))
    return TelegramUseCasesDependencies(
        identities_repo=PostgresUserIdentitiesRepository(),
        guests_repo=PostgresGuestsRepository(),
        admin_events_repo=PostgresAdminEventsRepository(),
        admin_insights_repo=PostgresAdminInsightsRepository(),
        rates_repo=PostgresDailyRatesRepository(),
        offers_repo=PostgresOffersRepository(),
        rules_repo=PostgresRulesRepository(),
        travelline_publish_report_repo=PostgresTravellinePublishReportRepository(),
        matches_run_repo=PostgresMatchesRunRepository(),
        desired_matches_run_repo=PostgresDesiredMatchesRunRepository(),
        notifications_repo=PostgresNotificationsRepository(),
        proactive_notification_cooldown_days=runtime_settings.proactive_notification_cooldown_days,
        matches_lookahead_days=runtime_settings.matches_lookahead_days,
        recalculation_coordinator=RecalculationRunCoordinator(advisory_lock_key=lock_key),
    )


def _build_travelline_rates_runner(
    *,
    runtime_settings: TelegramRuntimeSettings,
    deps: TelegramUseCasesDependencies,
) -> TravellineRatesParserRunner | None:
    travelline_requested = (
        runtime_settings.use_travelline_rates_source
        or runtime_settings.travelline_compare_only
        or runtime_settings.travelline_enable_publish
    )
    if not travelline_requested:
        return None
    if not runtime_settings.travelline_hotel_code:
        raise ValueError(
            "TRAVELLINE_HOTEL_CODE is required when Travelline rollout flags are enabled"
        )

    client = TravellineClient(
        base_url=runtime_settings.travelline_base_url,
        timeout_seconds=runtime_settings.travelline_timeout_seconds,
    )
    source = TravellineRatesSource(
        hotel_code=runtime_settings.travelline_hotel_code,
        hotel_info_gateway=TravellineHotelInfoGateway(client=client),
        availability_gateway=TravellineAvailabilityGateway(client=client),
        category_to_group=deps.rules_repo.get_category_to_group(),
        adults_counts=(1, 2, 3, 4, 5, 6),
    )
    return TravellineRatesParserRunner(
        source=source,
        rates_repo=deps.rates_repo,
        report_repo=deps.travelline_publish_report_repo,
        max_tariff_pairing_anomalies=runtime_settings.travelline_publish_max_tariff_pairing_anomalies,
        max_unmapped_categories=runtime_settings.travelline_publish_max_unmapped_categories,
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
