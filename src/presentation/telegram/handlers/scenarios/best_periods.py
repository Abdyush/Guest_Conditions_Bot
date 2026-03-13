from __future__ import annotations

import logging

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.main_menu import (
    build_best_group_inline_keyboard,
    build_best_period_details_inline_keyboard,
    build_phone_request_keyboard,
)
from src.presentation.telegram.presenters.message_presenter import render_best_periods
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)


class BestPeriodsScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def show_group_picker(self, message) -> None:
        await self._deps.sessions.set_state(message.from_user.id, ConversationState.AWAIT_BEST_GROUP_ID)
        await message.reply_text(msg("ask_best_group"), reply_markup=build_best_group_inline_keyboard())

    async def handle_best_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        group_id = data.split(":", 1)[1].strip().upper()
        try:
            picks = self._deps.adapter.get_best_periods(guest_id=guest_id, group_id=group_id, top_k=3)
            response = render_best_periods(guest_id=guest_id, group_id=group_id, picks=picks)
        except Exception:
            logger.exception("best_period_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("best_period_failed"))
            await self._deps.sessions.reset(telegram_user_id)
            return

        await query.answer()
        if query.message is not None:
            await query.message.reply_text(response, reply_markup=build_best_period_details_inline_keyboard())

    async def handle_back(self, telegram_user_id: int, message, guest_id: str) -> bool:
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state != ConversationState.AWAIT_BEST_GROUP_ID:
            return False
        await self._deps.sessions.reset(telegram_user_id)
        await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
        return True

    async def handle_nav_back_groups(self, telegram_user_id: int, query) -> None:
        await query.answer()
        await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_BEST_GROUP_ID)
        if query.message is not None:
            await query.edit_message_text(msg("ask_best_group"), reply_markup=build_best_group_inline_keyboard())
