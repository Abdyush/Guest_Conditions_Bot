from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.presentation.telegram.callbacks.data_parser import (
    NAV_BACK_AVAILABLE_CATEGORIES,
    NAV_BACK_BEST_CATEGORIES,
    NAV_BACK_BEST_GROUPS,
    NAV_BACK_MAIN,
    NAV_BACK_NOTIFIED_CATEGORIES,
    NAV_BACK_QUOTES_CALENDAR,
    NAV_BACK_QUOTES_CATEGORIES,
    NAV_BACK_QUOTES_GROUP,
    NAV_MAIN,
    PREFIX_AVAILABLE_CATEGORY,
    PREFIX_AVAILABLE_OFFER,
    PREFIX_AVAILABLE_PERIOD,
    PREFIX_BEST_GROUP,
    PREFIX_BEST_CATEGORY,
    PREFIX_BEST_OFFER,
    PREFIX_BEST_RESULT,
    PREFIX_CALENDAR,
    PREFIX_NOTIFIED_CATEGORY,
    PREFIX_NOTIFIED_OFFER,
    PREFIX_NOTIFIED_PERIOD,
    PREFIX_QUOTES_CATEGORY,
    PREFIX_QUOTES_OFFER,
    PREFIX_QUOTES_GROUP,
    PREFIX_QUOTES_RESULT,
    PREFIX_REGISTRATION_CATEGORY,
)
from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.scenarios.admin_commands import AdminCommandsScenario
from src.presentation.telegram.handlers.scenarios.available_offers import AvailableOffersScenario
from src.presentation.telegram.handlers.scenarios.best_periods import BestPeriodsScenario
from src.presentation.telegram.handlers.scenarios.onboarding import OnboardingScenario
from src.presentation.telegram.handlers.scenarios.period_quotes import PeriodQuotesScenario
from src.presentation.telegram.handlers.scenarios.registration import RegistrationScenario
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.navigation.flow_guard import TelegramFlowGuard
from src.presentation.telegram.keyboards.main_menu import (
    AVAILABLE_ROOMS_BUTTON,
    BACK_BUTTON,
    BEST_PERIOD_BUTTON,
    CANCEL_BUTTON,
    EDIT_DATA_BUTTON,
    MAIN_MENU_BUTTON,
    PERIOD_QUOTES_BUTTON,
    SCENARIO_BACK_BUTTON,
    build_edit_menu_keyboard,
    build_main_menu_keyboard,
    build_phone_request_keyboard,
    build_scenario_menu_keyboard,
)
from src.presentation.telegram.presenters.registration_presenter import render_phone_reminder
from src.presentation.telegram.services.pipeline_orchestrator import PipelineOrchestrator
from src.presentation.telegram.services.use_cases_adapter import TelegramUseCasesAdapter
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import InMemorySessionStore
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)

MAIN_MENU_ACTION_BUTTONS = {
    EDIT_DATA_BUTTON,
    AVAILABLE_ROOMS_BUTTON,
    PERIOD_QUOTES_BUTTON,
    BEST_PERIOD_BUTTON,
}


class TelegramBotHandlers:
    def __init__(self, *, adapter: TelegramUseCasesAdapter, sessions: InMemorySessionStore, pipeline: PipelineOrchestrator):
        flow_guard = TelegramFlowGuard(sessions=sessions)
        deps = TelegramHandlersDependencies(adapter=adapter, sessions=sessions, pipeline=pipeline, flow_guard=flow_guard)
        self._deps = deps
        self._onboarding = OnboardingScenario(deps=deps)
        self._registration = RegistrationScenario(deps=deps)
        self._best_periods = BestPeriodsScenario(deps=deps)
        self._period_quotes = PeriodQuotesScenario(deps=deps)
        self._available_offers = AvailableOffersScenario(deps=deps)
        self._admin_commands = AdminCommandsScenario(deps=deps)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._onboarding.start(update, context)

    async def unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._onboarding.unlink(update, context)

    async def parser_categ(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._admin_commands.parser_categ(update, context)

    async def parser_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._admin_commands.parser_offer(update, context)

    async def on_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._onboarding.on_contact(update, context)

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None:
            return
        data = query.data or ""
        logger.info("telegram_update type=callback user_id=%s data=%s", user.id, data)
        session = await self._deps.sessions.get(user.id)
        active_flow = session.active_flow

        if data == NAV_MAIN:
            await query.answer()
            guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=user.id)
            await self._deps.sessions.reset(user.id)
            if guest_id and query.message is not None:
                await send_main_menu_for_guest(deps=self._deps, message=query.message, guest_id=guest_id)
            return
        if data == NAV_BACK_MAIN:
            await query.answer()
            guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=user.id)
            if active_flow is not None:
                await self._deps.sessions.reset(user.id)
            if guest_id and query.message is not None:
                await send_main_menu_for_guest(deps=self._deps, message=query.message, guest_id=guest_id)
            return
        if data == NAV_BACK_QUOTES_GROUP:
            await self._period_quotes.handle_nav_back_group(user.id, query)
            return
        if data == NAV_BACK_BEST_GROUPS:
            await self._best_periods.handle_nav_back_groups(user.id, query)
            return
        if data == NAV_BACK_BEST_CATEGORIES:
            await self._best_periods.handle_nav_back_categories(user.id, query)
            return
        if data == NAV_BACK_AVAILABLE_CATEGORIES:
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return
            await self._available_offers.handle_nav_back_available_categories(user.id, query)
            return
        if data == NAV_BACK_NOTIFIED_CATEGORIES:
            await self._available_offers.handle_nav_back_notified_categories(user.id, query)
            return
        if data == NAV_BACK_QUOTES_CALENDAR:
            await self._period_quotes.handle_nav_back_calendar(user.id, query)
            return
        if data == NAV_BACK_QUOTES_CATEGORIES:
            await self._period_quotes.handle_nav_back_categories(user.id, query)
            return

        if active_flow == ActiveFlow.REGISTRATION and not self._is_registration_flow_callback(data):
            await query.answer()
            return
        if active_flow == ActiveFlow.AVAILABLE_ROOMS and not self._is_available_flow_callback(data):
            await query.answer()
            return
        if active_flow == ActiveFlow.BEST_PERIODS and not self._is_best_periods_flow_callback(data):
            await query.answer()
            return
        if active_flow == ActiveFlow.PERIOD_QUOTES and not self._is_period_quotes_flow_callback(data):
            await query.answer()
            return

        if data.startswith(PREFIX_BEST_GROUP):
            await self._best_periods.handle_best_group_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_BEST_CATEGORY):
            await self._best_periods.handle_best_category_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_BEST_OFFER):
            await self._best_periods.handle_best_offer_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_BEST_RESULT):
            await self._best_periods.handle_best_result_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_QUOTES_GROUP):
            await self._period_quotes.handle_quotes_group_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_CALENDAR):
            await self._period_quotes.handle_calendar_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_QUOTES_CATEGORY):
            await self._period_quotes.handle_quotes_category_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_QUOTES_OFFER):
            await self._period_quotes.handle_quotes_offer_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_QUOTES_RESULT):
            await self._period_quotes.handle_quotes_result_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_AVAILABLE_CATEGORY):
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return
            await self._available_offers.handle_available_category_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_AVAILABLE_PERIOD):
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return
            await self._available_offers.handle_available_period_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_AVAILABLE_OFFER):
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return
            await self._available_offers.handle_available_offer_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_REGISTRATION_CATEGORY):
            if active_flow != ActiveFlow.REGISTRATION and session.state != ConversationState.EDIT_GROUPS:
                await query.answer()
                return
            await self._registration.handle_categories_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_NOTIFIED_CATEGORY):
            await self._available_offers.handle_notified_category_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_NOTIFIED_PERIOD):
            await self._available_offers.handle_notified_period_callback(user.id, query, data)
            return
        if data.startswith(PREFIX_NOTIFIED_OFFER):
            await self._available_offers.handle_notified_offer_callback(user.id, query, data)
            return

        await query.answer()

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None or not message.text:
            return
        text = message.text.strip()
        logger.info("telegram_update type=text user_id=%s text=%s", user.id, text)

        if text == CANCEL_BUTTON:
            await self._deps.sessions.reset(user.id)
            await message.reply_text(msg("cancelled"), reply_markup=build_main_menu_keyboard())
            return

        session = await self._deps.sessions.get(user.id)
        if text == MAIN_MENU_BUTTON:
            await self._deps.sessions.reset(user.id)
            guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=user.id)
            if guest_id:
                await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            else:
                await self._deps.sessions.set_state(user.id, ConversationState.AWAIT_PHONE_CONTACT)
                await message.reply_text(msg("ask_phone"), reply_markup=build_phone_request_keyboard())
            return

        if text == BACK_BUTTON or text == SCENARIO_BACK_BUTTON:
            await self._handle_back(user.id, message)
            return

        if await self._registration.handle_flow_text(user.id, text, message):
            return
        if await self._available_offers.handle_flow_text(user.id, text, message):
            return
        if await self._best_periods.handle_flow_text(user.id, text, message):
            return
        if await self._period_quotes.handle_flow_text(user.id, text, message):
            return

        if session.state != ConversationState.IDLE and text in MAIN_MENU_ACTION_BUTTONS:
            return

        if text == EDIT_DATA_BUTTON:
            session.state = ConversationState.EDIT_MENU
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_keyboard())
            return

        if text == AVAILABLE_ROOMS_BUTTON:
            await self._available_offers.open_available_categories(user.id, message)
            return

        if text == BEST_PERIOD_BUTTON:
            await self._best_periods.open_group_picker(telegram_user_id=user.id, message=message)
            return

        if text == PERIOD_QUOTES_BUTTON:
            await self._period_quotes.open_group_picker(telegram_user_id=user.id, message=message)
            return

        if session.state == ConversationState.AWAIT_PHONE_CONTACT:
            await message.reply_text(render_phone_reminder(), reply_markup=build_phone_request_keyboard())
            return

        if session.state in {
            ConversationState.AWAIT_REG_ADULTS,
            ConversationState.AWAIT_REG_CHILDREN_4_13,
            ConversationState.AWAIT_REG_INFANTS_0_3,
            ConversationState.AWAIT_REG_GROUPS,
            ConversationState.AWAIT_REG_LOYALTY,
            ConversationState.AWAIT_REG_BANK,
            ConversationState.AWAIT_REG_DESIRED_PRICE,
        }:
            await self._registration.handle_registration_step(user.id, text, message)
            return

        if session.state in {
            ConversationState.EDIT_ADULTS,
            ConversationState.EDIT_CHILDREN_4_13,
            ConversationState.EDIT_INFANTS_0_3,
            ConversationState.EDIT_GROUPS,
            ConversationState.EDIT_LOYALTY,
            ConversationState.EDIT_BANK,
            ConversationState.EDIT_DESIRED_PRICE,
            ConversationState.EDIT_MENU,
        }:
            await self._registration.handle_edit_step(user.id, text, message)
            return

        if session.state in {
            ConversationState.AWAIT_QUOTES_GROUP,
            ConversationState.AWAIT_QUOTES_CALENDAR,
            ConversationState.AWAIT_QUOTES_CATEGORY,
        }:
            await message.reply_text(msg("quotes_use_calendar"))
            return

        await message.reply_text(msg("menu_hint"), reply_markup=build_main_menu_keyboard())

    async def _handle_back(self, telegram_user_id: int, message) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state in {
            ConversationState.AWAIT_REG_ADULTS,
            ConversationState.AWAIT_REG_CHILDREN_4_13,
            ConversationState.AWAIT_REG_INFANTS_0_3,
            ConversationState.AWAIT_REG_GROUPS,
            ConversationState.AWAIT_REG_LOYALTY,
            ConversationState.AWAIT_REG_BANK,
            ConversationState.AWAIT_REG_DESIRED_PRICE,
        }:
            guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
            if await self._registration.handle_back(telegram_user_id, message, guest_id):
                return

        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("ask_phone"), reply_markup=build_phone_request_keyboard())
            return

        if await self._registration.handle_back(telegram_user_id, message, guest_id):
            return
        if await self._period_quotes.handle_back(telegram_user_id, message, guest_id):
            return
        if await self._best_periods.handle_back(telegram_user_id, message, guest_id):
            return

        await self._deps.sessions.reset(telegram_user_id)
        await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)

    @staticmethod
    def _is_available_flow_callback(data: str) -> bool:
        return data == NAV_BACK_AVAILABLE_CATEGORIES or data.startswith(
            (
                PREFIX_AVAILABLE_CATEGORY,
                PREFIX_AVAILABLE_PERIOD,
                PREFIX_AVAILABLE_OFFER,
            )
        )

    @staticmethod
    def _is_registration_flow_callback(data: str) -> bool:
        return data.startswith(PREFIX_REGISTRATION_CATEGORY)

    @staticmethod
    def _is_period_quotes_flow_callback(data: str) -> bool:
        return data in {
            NAV_BACK_QUOTES_GROUP,
            NAV_BACK_QUOTES_CALENDAR,
            NAV_BACK_QUOTES_CATEGORIES,
        } or data.startswith(
            (
                PREFIX_QUOTES_GROUP,
                PREFIX_CALENDAR,
                PREFIX_QUOTES_CATEGORY,
                PREFIX_QUOTES_OFFER,
                PREFIX_QUOTES_RESULT,
            )
        )

    @staticmethod
    def _is_best_periods_flow_callback(data: str) -> bool:
        return data in {
            NAV_BACK_BEST_GROUPS,
            NAV_BACK_BEST_CATEGORIES,
        } or data.startswith(
            (
                PREFIX_BEST_GROUP,
                PREFIX_BEST_CATEGORY,
                PREFIX_BEST_OFFER,
                PREFIX_BEST_RESULT,
            )
        )
