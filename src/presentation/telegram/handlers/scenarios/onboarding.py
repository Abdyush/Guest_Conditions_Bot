from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.main_menu import build_phone_request_keyboard
from src.presentation.telegram.keyboards.registration import build_registration_numeric_keyboard
from src.presentation.telegram.mappers.value_parser import telegram_profile_name
from src.presentation.telegram.presenters.registration_presenter import (
    render_adults_prompt,
    render_registration_intro,
    render_welcome_message,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import RegistrationDraft
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)


class OnboardingScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        try:
            logger.info("telegram_update type=start user_id=%s", user.id)
            guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=user.id)
            if guest_id:
                await self._deps.sessions.reset(user.id)
                await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
                return

            await self._deps.sessions.set_state(user.id, ConversationState.AWAIT_PHONE_CONTACT)
            session = await self._deps.sessions.get(user.id)
            session.registration = None
            await message.reply_text(render_welcome_message(), reply_markup=build_phone_request_keyboard())
        finally:
            await self._deps.sessions.persist(user.id)

    async def unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        try:
            self._deps.identity.unbind_telegram(telegram_user_id=user.id)
            await self._deps.sessions.reset(user.id)
            await message.reply_text(msg("unlink_done"), reply_markup=build_phone_request_keyboard())
        finally:
            await self._deps.sessions.persist(user.id)

    async def on_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None or message.contact is None:
            return
        logger.info("telegram_update type=contact user_id=%s", user.id)

        if message.contact.user_id is not None and message.contact.user_id != user.id:
            await message.reply_text(msg("send_own_phone"), reply_markup=build_phone_request_keyboard())
            await self._deps.sessions.persist(user.id)
            return

        guest_id = self._deps.identity.bind_by_phone(telegram_user_id=user.id, phone=message.contact.phone_number)
        if guest_id:
            await self._deps.sessions.reset(user.id)
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            await self._deps.sessions.persist(user.id)
            return

        session = await self._deps.sessions.get(user.id)
        session.registration = RegistrationDraft(
            phone=message.contact.phone_number,
            name=telegram_profile_name(user),
            allowed_groups=set(),
        )
        await self._deps.flow_guard.enter(user.id, ActiveFlow.REGISTRATION)
        session.state = ConversationState.AWAIT_REG_ADULTS
        await message.reply_text(render_registration_intro())
        await message.reply_text(render_adults_prompt(), reply_markup=build_registration_numeric_keyboard())
        await self._deps.sessions.persist(user.id)

