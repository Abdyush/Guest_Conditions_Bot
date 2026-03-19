from __future__ import annotations

import logging

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.scenario_registry import TelegramScenarioRegistry
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.main_menu import (
    AVAILABLE_ROOMS_BUTTON,
    BACK_BUTTON,
    BEST_PERIOD_BUTTON,
    CANCEL_BUTTON,
    EDIT_DATA_BUTTON,
    MAIN_MENU_BUTTON,
    PERIOD_QUOTES_BUTTON,
    SCENARIO_BACK_BUTTON,
    build_main_menu_keyboard,
    build_phone_request_keyboard,
)
from src.presentation.telegram.presenters.registration_presenter import render_phone_reminder
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)

MAIN_MENU_ACTION_BUTTONS = {
    EDIT_DATA_BUTTON,
    AVAILABLE_ROOMS_BUTTON,
    PERIOD_QUOTES_BUTTON,
    BEST_PERIOD_BUTTON,
}


class TelegramTextRouter:
    def __init__(self, *, deps: TelegramHandlersDependencies, scenarios: TelegramScenarioRegistry):
        self._deps = deps
        self._scenarios = scenarios

    async def dispatch(self, *, user_id: int, message, text: str) -> None:
        logger.info("telegram_update type=text user_id=%s text=%s", user_id, text)

        if text == CANCEL_BUTTON:
            await self._deps.sessions.reset(user_id)
            await message.reply_text(msg("cancelled"), reply_markup=build_main_menu_keyboard())
            return

        session = await self._deps.sessions.get(user_id)
        if text == MAIN_MENU_BUTTON:
            await self._deps.sessions.reset(user_id)
            guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=user_id)
            if guest_id:
                await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            else:
                await self._deps.sessions.set_state(user_id, ConversationState.AWAIT_PHONE_CONTACT)
                await message.reply_text(msg("ask_phone"), reply_markup=build_phone_request_keyboard())
            return

        if text == BACK_BUTTON or text == SCENARIO_BACK_BUTTON:
            await self._handle_back(user_id, message)
            return

        if await self._scenarios.registration.handle_flow_text(user_id, text, message):
            return
        if await self._scenarios.admin_menu.handle_flow_text(user_id, text, message):
            return
        if await self._scenarios.available_offers.handle_flow_text(user_id, text, message):
            return
        if await self._scenarios.best_periods.handle_flow_text(user_id, text, message):
            return
        if await self._scenarios.notification_offers.handle_flow_text(user_id, message):
            return
        if await self._scenarios.period_quotes.handle_flow_text(user_id, text, message):
            return

        if session.state != ConversationState.IDLE and text in MAIN_MENU_ACTION_BUTTONS:
            return

        if text == EDIT_DATA_BUTTON:
            await self._scenarios.registration.open_edit_menu(user_id, message)
            return

        if text == AVAILABLE_ROOMS_BUTTON:
            await self._scenarios.available_offers.open_available_categories(user_id, message)
            return

        if text == BEST_PERIOD_BUTTON:
            await self._scenarios.best_periods.open_group_picker(telegram_user_id=user_id, message=message)
            return

        if text == PERIOD_QUOTES_BUTTON:
            await self._scenarios.period_quotes.open_group_picker(telegram_user_id=user_id, message=message)
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
            await self._scenarios.registration.handle_registration_step(user_id, text, message)
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
            await self._scenarios.registration.handle_edit_step(user_id, text, message)
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
            guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
            if await self._scenarios.registration.handle_back(telegram_user_id, message, guest_id):
                return

        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("ask_phone"), reply_markup=build_phone_request_keyboard())
            return

        if await self._scenarios.registration.handle_back(telegram_user_id, message, guest_id):
            return
        if await self._scenarios.admin_menu.handle_back(telegram_user_id, message):
            return
        if await self._scenarios.period_quotes.handle_back(telegram_user_id, message, guest_id):
            return
        if await self._scenarios.best_periods.handle_back(telegram_user_id, message, guest_id):
            return

        await self._deps.sessions.reset(telegram_user_id)
        await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)

