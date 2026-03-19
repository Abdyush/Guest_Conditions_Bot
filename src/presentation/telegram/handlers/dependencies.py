from __future__ import annotations

from dataclasses import dataclass

from src.infrastructure.orchestration.pipeline_orchestrator import PipelineOrchestrator
from src.presentation.telegram.navigation.flow_guard import TelegramFlowGuard
from src.presentation.telegram.services.use_cases_adapter import (
    TelegramAdminFacade,
    TelegramAvailableOffersFacade,
    TelegramBestPeriodsFacade,
    TelegramIdentityFacade,
    TelegramNotificationsFacade,
    TelegramPeriodQuotesFacade,
    TelegramPresentationServices,
    TelegramProfileFacade,
    TelegramSystemFacade,
)
from src.presentation.telegram.state.session_store import InMemorySessionStore


@dataclass(frozen=True, slots=True)
class TelegramHandlersDependencies:
    identity: TelegramIdentityFacade
    profile: TelegramProfileFacade
    available_offers: TelegramAvailableOffersFacade
    best_periods: TelegramBestPeriodsFacade
    period_quotes: TelegramPeriodQuotesFacade
    notifications: TelegramNotificationsFacade
    admin: TelegramAdminFacade
    system: TelegramSystemFacade
    sessions: InMemorySessionStore
    pipeline: PipelineOrchestrator
    flow_guard: TelegramFlowGuard
    admin_telegram_id: int | None


def build_handlers_dependencies(
    *,
    services: TelegramPresentationServices,
    sessions: InMemorySessionStore,
    pipeline: PipelineOrchestrator,
    flow_guard: TelegramFlowGuard,
    admin_telegram_id: int | None,
) -> TelegramHandlersDependencies:
    return TelegramHandlersDependencies(
        identity=services.identity,
        profile=services.profile,
        available_offers=services.available_offers,
        best_periods=services.best_periods,
        period_quotes=services.period_quotes,
        notifications=services.notifications,
        admin=services.admin,
        system=services.system,
        sessions=sessions,
        pipeline=pipeline,
        flow_guard=flow_guard,
        admin_telegram_id=admin_telegram_id,
    )
