from __future__ import annotations

import logging

from src.presentation.telegram.callbacks.data_parser import (
    NAV_BACK_AVAILABLE_CATEGORIES,
    NAV_BACK_BEST_CATEGORIES,
    NAV_BACK_BEST_GROUPS,
    NAV_BACK_MAIN,
    NAV_BACK_NOTIFICATION_GROUPS,
    NAV_BACK_NOTIFIED_CATEGORIES,
    NAV_BACK_QUOTES_CALENDAR,
    NAV_BACK_QUOTES_CATEGORIES,
    NAV_BACK_QUOTES_GROUP,
    NAV_MAIN,
    PREFIX_ADMIN,
    PREFIX_AVAILABLE_CATEGORY,
    PREFIX_AVAILABLE_OFFER,
    PREFIX_AVAILABLE_PERIOD,
    PREFIX_INTEREST_REQUEST,
    PREFIX_BEST_CATEGORY,
    PREFIX_BEST_GROUP,
    PREFIX_EDIT_BANK,
    PREFIX_EDIT_FIELD,
    PREFIX_EDIT_LOYALTY,
    PREFIX_EDIT_NAV,
    PREFIX_BEST_OFFER,
    PREFIX_BEST_RESULT,
    PREFIX_CALENDAR,
    PREFIX_NOTIFICATION_CATEGORY,
    PREFIX_NOTIFICATION_GROUP,
    PREFIX_NOTIFICATION_OFFER,
    PREFIX_NOTIFICATION_PERIOD,
    PREFIX_NOTIFIED_CATEGORY,
    PREFIX_NOTIFIED_OFFER,
    PREFIX_NOTIFIED_PERIOD,
    PREFIX_QUOTES_CATEGORY,
    PREFIX_QUOTES_GROUP,
    PREFIX_QUOTES_OFFER,
    PREFIX_QUOTES_RESULT,
    PREFIX_REGISTRATION_BANK,
    PREFIX_REGISTRATION_CATEGORY,
    PREFIX_REGISTRATION_LOYALTY,
)
from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.scenario_registry import TelegramScenarioRegistry
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState


logger = logging.getLogger(__name__)


class TelegramCallbackDispatcher:
    def __init__(self, *, deps: TelegramHandlersDependencies, scenarios: TelegramScenarioRegistry):
        self._deps = deps
        self._scenarios = scenarios

    async def dispatch(self, *, user_id: int, query, data: str) -> None:
        logger.info("telegram_update type=callback user_id=%s data=%s", user_id, data)
        session = await self._deps.sessions.get(user_id)
        active_flow = session.active_flow

        if await self._handle_navigation(user_id=user_id, query=query, data=data, active_flow=active_flow):
            return
        if self._is_foreign_flow_callback(active_flow=active_flow, session_state=session.state, data=data):
            await query.answer()
            return
        if await self._dispatch_scenario_callback(user_id=user_id, query=query, data=data, active_flow=active_flow, session_state=session.state):
            return

        await query.answer()

    async def _handle_navigation(self, *, user_id: int, query, data: str, active_flow: ActiveFlow | None) -> bool:
        if data == NAV_MAIN:
            await query.answer()
            guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=user_id)
            await self._deps.sessions.reset(user_id)
            if guest_id and query.message is not None:
                await send_main_menu_for_guest(deps=self._deps, message=query.message, guest_id=guest_id)
            return True
        if data == NAV_BACK_MAIN:
            await query.answer()
            guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=user_id)
            if active_flow is not None:
                await self._deps.sessions.reset(user_id)
            if guest_id and query.message is not None:
                await send_main_menu_for_guest(deps=self._deps, message=query.message, guest_id=guest_id)
            return True
        if data == NAV_BACK_QUOTES_GROUP:
            await self._scenarios.period_quotes.handle_nav_back_group(user_id, query)
            return True
        if data == NAV_BACK_BEST_GROUPS:
            await self._scenarios.best_periods.handle_nav_back_groups(user_id, query)
            return True
        if data == NAV_BACK_BEST_CATEGORIES:
            await self._scenarios.best_periods.handle_nav_back_categories(user_id, query)
            return True
        if data.startswith(NAV_BACK_NOTIFICATION_GROUPS):
            if active_flow not in {None, ActiveFlow.NOTIFICATION_OFFERS}:
                await query.answer()
                return True
            await self._scenarios.notification_offers.handle_nav_back_groups(user_id, query, data)
            return True
        if data == NAV_BACK_AVAILABLE_CATEGORIES:
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return True
            await self._scenarios.available_offers.handle_nav_back_available_categories(user_id, query)
            return True
        if data == NAV_BACK_NOTIFIED_CATEGORIES:
            await self._scenarios.available_offers.handle_nav_back_notified_categories(user_id, query)
            return True
        if data == NAV_BACK_QUOTES_CALENDAR:
            await self._scenarios.period_quotes.handle_nav_back_calendar(user_id, query)
            return True
        if data == NAV_BACK_QUOTES_CATEGORIES:
            await self._scenarios.period_quotes.handle_nav_back_categories(user_id, query)
            return True
        return False

    def _is_foreign_flow_callback(
        self,
        *,
        active_flow: ActiveFlow | None,
        session_state: ConversationState,
        data: str,
    ) -> bool:
        if active_flow == ActiveFlow.REGISTRATION and not self._is_registration_flow_callback(data, session_state):
            return True
        if active_flow == ActiveFlow.ADMIN_MENU and not self._is_admin_flow_callback(data):
            return True
        if active_flow == ActiveFlow.AVAILABLE_ROOMS and not self._is_available_flow_callback(data):
            return True
        if active_flow == ActiveFlow.BEST_PERIODS and not self._is_best_periods_flow_callback(data):
            return True
        if active_flow == ActiveFlow.NOTIFICATION_OFFERS and not self._is_notification_flow_callback(data):
            return True
        if active_flow == ActiveFlow.PERIOD_QUOTES and not self._is_period_quotes_flow_callback(data):
            return True
        return False

    async def _dispatch_scenario_callback(
        self,
        *,
        user_id: int,
        query,
        data: str,
        active_flow: ActiveFlow | None,
        session_state: ConversationState,
    ) -> bool:
        if data.startswith(PREFIX_BEST_GROUP):
            await self._scenarios.best_periods.handle_best_group_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_ADMIN):
            await self._scenarios.admin_menu.handle_admin_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_BEST_CATEGORY):
            await self._scenarios.best_periods.handle_best_category_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_BEST_OFFER):
            await self._scenarios.best_periods.handle_best_offer_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_BEST_RESULT):
            await self._scenarios.best_periods.handle_best_result_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFICATION_GROUP):
            if active_flow not in {None, ActiveFlow.NOTIFICATION_OFFERS}:
                await query.answer()
                return True
            await self._scenarios.notification_offers.handle_group_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFICATION_CATEGORY):
            if active_flow not in {None, ActiveFlow.NOTIFICATION_OFFERS}:
                await query.answer()
                return True
            await self._scenarios.notification_offers.handle_category_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFICATION_PERIOD):
            if active_flow not in {None, ActiveFlow.NOTIFICATION_OFFERS}:
                await query.answer()
                return True
            await self._scenarios.notification_offers.handle_period_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFICATION_OFFER):
            if active_flow not in {None, ActiveFlow.NOTIFICATION_OFFERS}:
                await query.answer()
                return True
            await self._scenarios.notification_offers.handle_offer_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_QUOTES_GROUP):
            await self._scenarios.period_quotes.handle_quotes_group_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_CALENDAR):
            await self._scenarios.period_quotes.handle_calendar_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_QUOTES_CATEGORY):
            await self._scenarios.period_quotes.handle_quotes_category_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_QUOTES_OFFER):
            await self._scenarios.period_quotes.handle_quotes_offer_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_QUOTES_RESULT):
            await self._scenarios.period_quotes.handle_quotes_result_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_AVAILABLE_CATEGORY):
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return True
            await self._scenarios.available_offers.handle_available_category_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_INTEREST_REQUEST):
            if active_flow == ActiveFlow.AVAILABLE_ROOMS:
                await self._scenarios.available_offers.handle_interest_request_callback(user_id, query, data)
                return True
            if active_flow == ActiveFlow.PERIOD_QUOTES:
                await self._scenarios.period_quotes.handle_interest_request_callback(user_id, query, data)
                return True
            if active_flow == ActiveFlow.BEST_PERIODS:
                await self._scenarios.best_periods.handle_interest_request_callback(user_id, query, data)
                return True
            await query.answer()
            return True
        if data.startswith(PREFIX_AVAILABLE_PERIOD):
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return True
            await self._scenarios.available_offers.handle_available_period_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_AVAILABLE_OFFER):
            if active_flow != ActiveFlow.AVAILABLE_ROOMS:
                await query.answer()
                return True
            await self._scenarios.available_offers.handle_available_offer_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_EDIT_FIELD):
            if session_state != ConversationState.EDIT_MENU:
                await query.answer()
                return True
            await self._scenarios.registration.handle_edit_field_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_EDIT_LOYALTY):
            if session_state != ConversationState.EDIT_LOYALTY:
                await query.answer()
                return True
            await self._scenarios.registration.handle_edit_loyalty_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_EDIT_BANK):
            if session_state != ConversationState.EDIT_BANK:
                await query.answer()
                return True
            await self._scenarios.registration.handle_edit_bank_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_EDIT_NAV):
            if session_state not in {
                ConversationState.EDIT_ADULTS,
                ConversationState.EDIT_CHILDREN_4_13,
                ConversationState.EDIT_INFANTS_0_3,
                ConversationState.EDIT_GROUPS,
                ConversationState.EDIT_LOYALTY,
                ConversationState.EDIT_BANK,
                ConversationState.EDIT_DESIRED_PRICE,
            }:
                await query.answer()
                return True
            await self._scenarios.registration.handle_edit_navigation_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_REGISTRATION_CATEGORY):
            if active_flow != ActiveFlow.REGISTRATION and session_state != ConversationState.EDIT_GROUPS:
                await query.answer()
                return True
            await self._scenarios.registration.handle_categories_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_REGISTRATION_LOYALTY):
            if session_state != ConversationState.AWAIT_REG_LOYALTY:
                await query.answer()
                return True
            await self._scenarios.registration.handle_registration_loyalty_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_REGISTRATION_BANK):
            if session_state != ConversationState.AWAIT_REG_BANK:
                await query.answer()
                return True
            await self._scenarios.registration.handle_registration_bank_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFIED_CATEGORY):
            await self._scenarios.available_offers.handle_notified_category_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFIED_PERIOD):
            await self._scenarios.available_offers.handle_notified_period_callback(user_id, query, data)
            return True
        if data.startswith(PREFIX_NOTIFIED_OFFER):
            await self._scenarios.available_offers.handle_notified_offer_callback(user_id, query, data)
            return True
        return False

    @staticmethod
    def _is_available_flow_callback(data: str) -> bool:
        return data == NAV_BACK_AVAILABLE_CATEGORIES or data.startswith(
            (
                PREFIX_AVAILABLE_CATEGORY,
                PREFIX_INTEREST_REQUEST,
                PREFIX_AVAILABLE_PERIOD,
                PREFIX_AVAILABLE_OFFER,
            )
        )

    @staticmethod
    def _is_registration_flow_callback(data: str, session_state: ConversationState) -> bool:
        return (
            data.startswith(PREFIX_REGISTRATION_CATEGORY)
            or data.startswith(PREFIX_REGISTRATION_LOYALTY)
            or data.startswith(PREFIX_REGISTRATION_BANK)
            or session_state == ConversationState.EDIT_GROUPS
        )

    @staticmethod
    def _is_admin_flow_callback(data: str) -> bool:
        return data.startswith(PREFIX_ADMIN)

    @staticmethod
    def _is_period_quotes_flow_callback(data: str) -> bool:
        return data in {
            NAV_BACK_QUOTES_GROUP,
            NAV_BACK_QUOTES_CALENDAR,
            NAV_BACK_QUOTES_CATEGORIES,
        } or data.startswith(
            (
                PREFIX_INTEREST_REQUEST,
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
                PREFIX_INTEREST_REQUEST,
                PREFIX_BEST_GROUP,
                PREFIX_BEST_CATEGORY,
                PREFIX_BEST_OFFER,
                PREFIX_BEST_RESULT,
            )
        )

    @staticmethod
    def _is_notification_flow_callback(data: str) -> bool:
        return data.startswith(NAV_BACK_NOTIFICATION_GROUPS) or data.startswith(
            (
                PREFIX_NOTIFICATION_GROUP,
                PREFIX_NOTIFICATION_CATEGORY,
                PREFIX_NOTIFICATION_PERIOD,
                PREFIX_NOTIFICATION_OFFER,
            )
        )

