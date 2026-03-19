from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.infrastructure.orchestration.pipeline_orchestrator import PipelineOrchestrator
from src.presentation.telegram.handlers.callback_dispatcher import TelegramCallbackDispatcher
from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies, build_handlers_dependencies
from src.presentation.telegram.handlers.scenario_registry import TelegramScenarioRegistry
from src.presentation.telegram.handlers.scenarios.admin_commands import AdminCommandsScenario
from src.presentation.telegram.handlers.scenarios.admin_menu import AdminMenuScenario
from src.presentation.telegram.handlers.scenarios.available_offers import AvailableOffersScenario
from src.presentation.telegram.handlers.scenarios.best_periods import BestPeriodsScenario
from src.presentation.telegram.handlers.scenarios.notification_offers import NotificationOffersScenario
from src.presentation.telegram.handlers.scenarios.onboarding import OnboardingScenario
from src.presentation.telegram.handlers.scenarios.period_quotes import PeriodQuotesScenario
from src.presentation.telegram.handlers.scenarios.registration import RegistrationScenario
from src.presentation.telegram.handlers.text_router import TelegramTextRouter
from src.presentation.telegram.navigation.flow_guard import TelegramFlowGuard
from src.presentation.telegram.services.use_cases_adapter import TelegramPresentationServices
from src.presentation.telegram.state.session_store import InMemorySessionStore


class TelegramBotHandlers:
    def __init__(
        self,
        *,
        services: TelegramPresentationServices,
        sessions: InMemorySessionStore,
        pipeline: PipelineOrchestrator,
        admin_telegram_id: int | None,
    ):
        flow_guard = TelegramFlowGuard(sessions=sessions)
        deps = build_handlers_dependencies(
            services=services,
            sessions=sessions,
            pipeline=pipeline,
            flow_guard=flow_guard,
            admin_telegram_id=admin_telegram_id,
        )
        self._deps = deps
        self._scenarios = TelegramScenarioRegistry(
            onboarding=OnboardingScenario(deps=deps),
            registration=RegistrationScenario(deps=deps),
            admin_menu=AdminMenuScenario(deps=deps),
            best_periods=BestPeriodsScenario(deps=deps),
            period_quotes=PeriodQuotesScenario(deps=deps),
            available_offers=AvailableOffersScenario(deps=deps),
            notification_offers=NotificationOffersScenario(deps=deps),
            admin_commands=AdminCommandsScenario(deps=deps),
        )
        self._callback_dispatcher = TelegramCallbackDispatcher(deps=deps, scenarios=self._scenarios)
        self._text_router = TelegramTextRouter(deps=deps, scenarios=self._scenarios)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._scenarios.onboarding.start(update, context)

    async def unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._scenarios.onboarding.unlink(update, context)

    async def parser_categ(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._scenarios.admin_commands.parser_categ(update, context)

    async def parser_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._scenarios.admin_commands.parser_offer(update, context)

    async def admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._scenarios.admin_menu.open_admin_menu(update, context)

    async def on_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._scenarios.onboarding.on_contact(update, context)

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None:
            return
        await self._callback_dispatcher.dispatch(user_id=user.id, query=query, data=query.data or "")

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None or not message.text:
            return
        await self._text_router.dispatch(user_id=user.id, message=message, text=message.text.strip())
