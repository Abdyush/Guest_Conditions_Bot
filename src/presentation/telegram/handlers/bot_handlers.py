
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from telegram import Update
from telegram.ext import ContextTypes

from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.dto.period_quote import PeriodQuote
from src.domain.entities.guest_preferences import GuestPreferences
from src.presentation.telegram.keyboards.calendar_picker import build_period_calendar_keyboard, first_day_of_month
from src.presentation.telegram.keyboards.main_menu import (
    AVAILABLE_ROOMS_BUTTON,
    BACK_BUTTON,
    BEST_PERIOD_BUTTON,
    CANCEL_BUTTON,
    EDIT_ADULTS_BUTTON,
    EDIT_BANK_BUTTON,
    EDIT_CHILDREN_BUTTON,
    EDIT_DATA_BUTTON,
    EDIT_GROUPS_BUTTON,
    EDIT_INFANTS_BUTTON,
    EDIT_LOYALTY_BUTTON,
    EDIT_PRICE_BUTTON,
    PERIOD_QUOTES_BUTTON,
    build_available_categories_inline_keyboard,
    build_available_period_details_inline_keyboard,
    build_available_periods_inline_keyboard,
    build_bank_keyboard,
    build_best_period_details_inline_keyboard,
    build_best_group_inline_keyboard,
    build_categories_inline_keyboard,
    build_edit_menu_keyboard,
    build_loyalty_keyboard,
    build_main_menu_keyboard,
    build_numeric_edit_keyboard,
    build_phone_request_keyboard,
    build_quotes_categories_inline_keyboard,
    build_quotes_category_details_inline_keyboard,
    build_quotes_group_inline_keyboard,
)
from src.presentation.telegram.presenters.message_presenter import render_best_periods, render_period_quotes
from src.presentation.telegram.services.use_cases_adapter import TelegramUseCasesAdapter
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import InMemorySessionStore, PeriodQuotesDraft, RegistrationDraft
from src.presentation.telegram.ui_texts import BANK_LABEL_TO_CODE, CATEGORY_LABEL_TO_CODE, LOYALTY_OPTIONS, msg


logger = logging.getLogger(__name__)


class AvailablePeriod(NamedTuple):
    start: date
    end: date
    min_new_price_minor: int
    rows: list[MatchedDateRecord]


class TelegramBotHandlers:
    def __init__(self, *, adapter: TelegramUseCasesAdapter, sessions: InMemorySessionStore):
        self._adapter = adapter
        self._sessions = sessions

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        logger.info("telegram_update type=start user_id=%s", user.id)

        guest_id = self._adapter.resolve_guest_id(telegram_user_id=user.id)
        if guest_id:
            self._sessions.reset(user.id)
            await self._send_main_menu_for_guest(message=message, guest_id=guest_id)
            return

        self._sessions.set_state(user.id, ConversationState.AWAIT_PHONE_CONTACT)
        self._sessions.get(user.id).registration = None
        await message.reply_text(msg("ask_phone"), reply_markup=build_phone_request_keyboard())

    async def unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        self._adapter.unbind_telegram(telegram_user_id=user.id)
        self._sessions.reset(user.id)
        await message.reply_text(msg("unlink_done"), reply_markup=build_phone_request_keyboard())

    async def on_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None or message.contact is None:
            return
        logger.info("telegram_update type=contact user_id=%s", user.id)

        if message.contact.user_id is not None and message.contact.user_id != user.id:
            await message.reply_text(msg("send_own_phone"), reply_markup=build_phone_request_keyboard())
            return

        guest_id = self._adapter.bind_by_phone(telegram_user_id=user.id, phone=message.contact.phone_number)
        if guest_id:
            self._sessions.reset(user.id)
            await self._send_main_menu_for_guest(message=message, guest_id=guest_id)
            return

        session = self._sessions.get(user.id)
        session.registration = RegistrationDraft(
            phone=message.contact.phone_number,
            name=self._telegram_profile_name(user),
            allowed_groups=set(),
        )
        session.state = ConversationState.AWAIT_REG_ADULTS
        await message.reply_text(msg("registration_start"), reply_markup=build_numeric_edit_keyboard())

    async def on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None:
            return
        data = query.data or ""
        logger.info("telegram_update type=callback user_id=%s data=%s", user.id, data)

        if data == "nav:main":
            await query.answer()
            guest_id = self._adapter.resolve_guest_id(telegram_user_id=user.id)
            self._sessions.reset(user.id)
            if guest_id and query.message is not None:
                await self._send_main_menu_for_guest(message=query.message, guest_id=guest_id)
            return
        if data == "nav:back_main":
            await query.answer()
            guest_id = self._adapter.resolve_guest_id(telegram_user_id=user.id)
            if guest_id and query.message is not None:
                await self._send_main_menu_for_guest(message=query.message, guest_id=guest_id)
            return
        if data == "nav:back_quotes_group":
            await query.answer()
            session = self._sessions.get(user.id)
            session.state = ConversationState.AWAIT_QUOTES_GROUP
            if query.message is not None:
                await query.edit_message_text(msg("ask_quotes_group"), reply_markup=build_quotes_group_inline_keyboard())
            return
        if data == "nav:back_best_groups":
            await query.answer()
            self._sessions.set_state(user.id, ConversationState.AWAIT_BEST_GROUP_ID)
            if query.message is not None:
                await query.edit_message_text(msg("ask_best_group"), reply_markup=build_best_group_inline_keyboard())
            return
        if data == "nav:back_avail_categories":
            await query.answer()
            session = self._sessions.get(user.id)
            categories = session.available_category_names or []
            if query.message is not None:
                await query.edit_message_text(
                    msg("available_pick_category"),
                    reply_markup=build_available_categories_inline_keyboard(category_names=categories),
                )
            return
        if data == "nav:back_quotes_calendar":
            await query.answer()
            session = self._sessions.get(user.id)
            draft = session.period_quotes
            if draft is None or draft.month_cursor is None:
                return
            session.state = ConversationState.AWAIT_QUOTES_CALENDAR
            if query.message is not None:
                await query.edit_message_text(
                    text=msg("ask_quotes_calendar"),
                    reply_markup=build_period_calendar_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                    ),
                )
            return
        if data == "nav:back_quotes_categories":
            await query.answer()
            session = self._sessions.get(user.id)
            draft = session.period_quotes
            if draft is None:
                return
            session.state = ConversationState.AWAIT_QUOTES_CATEGORY
            category_names = draft.category_names or []
            if query.message is not None:
                await query.edit_message_text(
                    "Выберите категорию:",
                    reply_markup=build_quotes_categories_inline_keyboard(category_names=category_names),
                )
            return

        if data.startswith("bestgrp:"):
            await self._handle_best_group_callback(user.id, query, data)
            return
        if data.startswith("qgrp:"):
            await self._handle_quotes_group_callback(user.id, query, data)
            return
        if data.startswith("cal:"):
            await self._handle_calendar_callback(user.id, query, data)
            return
        if data.startswith("qcat:"):
            await self._handle_quotes_category_callback(user.id, query, data)
            return
        if data.startswith("availcat:"):
            await self._handle_available_category_callback(user.id, query, data)
            return
        if data.startswith("availprd:"):
            await self._handle_available_period_callback(user.id, query, data)
            return
        if data.startswith("regcat:"):
            await self._handle_categories_callback(user.id, query, data)
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
            self._sessions.reset(user.id)
            await message.reply_text(msg("cancelled"), reply_markup=build_main_menu_keyboard())
            return

        session = self._sessions.get(user.id)
        if text == BACK_BUTTON:
            await self._handle_back(user.id, message)
            return

        if text == EDIT_DATA_BUTTON:
            session.state = ConversationState.EDIT_MENU
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_keyboard())
            return

        if text == AVAILABLE_ROOMS_BUTTON:
            await self._open_available_categories(user.id, message)
            return

        if text == BEST_PERIOD_BUTTON:
            self._sessions.set_state(user.id, ConversationState.AWAIT_BEST_GROUP_ID)
            await message.reply_text(msg("ask_best_group"), reply_markup=build_best_group_inline_keyboard())
            return

        if text == PERIOD_QUOTES_BUTTON:
            self._sessions.set_state(user.id, ConversationState.AWAIT_QUOTES_GROUP)
            self._sessions.get(user.id).period_quotes = None
            await message.reply_text(msg("ask_quotes_group"), reply_markup=build_quotes_group_inline_keyboard())
            return

        if session.state == ConversationState.AWAIT_PHONE_CONTACT:
            await message.reply_text(msg("phone_only"), reply_markup=build_phone_request_keyboard())
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
            await self._handle_registration_step(user.id, text, message)
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
            await self._handle_edit_step(user.id, text, message)
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
        session = self._sessions.get(telegram_user_id)
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("ask_phone"), reply_markup=build_phone_request_keyboard())
            return

        if session.state in {
            ConversationState.EDIT_ADULTS,
            ConversationState.EDIT_CHILDREN_4_13,
            ConversationState.EDIT_INFANTS_0_3,
            ConversationState.EDIT_GROUPS,
            ConversationState.EDIT_LOYALTY,
            ConversationState.EDIT_BANK,
            ConversationState.EDIT_DESIRED_PRICE,
        }:
            session.state = ConversationState.EDIT_MENU
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_keyboard())
            return

        self._sessions.reset(telegram_user_id)
        await self._send_main_menu_for_guest(message=message, guest_id=guest_id)

    async def _handle_registration_step(self, telegram_user_id: int, text: str, message) -> None:
        session = self._sessions.get(telegram_user_id)
        reg = session.registration
        if reg is None:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("send_phone_first"), reply_markup=build_phone_request_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_ADULTS:
            adults = self._parse_int(text)
            if adults is None or adults < 1:
                await message.reply_text(msg("reg_adults_invalid"), reply_markup=build_numeric_edit_keyboard())
                return
            reg.adults = adults
            session.state = ConversationState.AWAIT_REG_CHILDREN_4_13
            await message.reply_text(msg("reg_step_3"), reply_markup=build_numeric_edit_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_CHILDREN_4_13:
            children = self._parse_int(text)
            if children is None or children < 0:
                await message.reply_text(msg("reg_children_invalid"), reply_markup=build_numeric_edit_keyboard())
                return
            reg.children_4_13 = children
            session.state = ConversationState.AWAIT_REG_INFANTS_0_3
            await message.reply_text(msg("reg_step_4"), reply_markup=build_numeric_edit_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_INFANTS_0_3:
            infants = self._parse_int(text)
            if infants is None or infants < 0:
                await message.reply_text(msg("reg_infants_invalid"), reply_markup=build_numeric_edit_keyboard())
                return
            reg.infants_0_3 = infants
            session.state = ConversationState.AWAIT_REG_GROUPS
            await message.reply_text(msg("reg_step_5"), reply_markup=build_categories_inline_keyboard(selected_codes=reg.allowed_groups or set()))
            return

        if session.state == ConversationState.AWAIT_REG_GROUPS:
            await message.reply_text(msg("reg_groups_use_buttons"))
            return

        if session.state == ConversationState.AWAIT_REG_LOYALTY:
            if text not in LOYALTY_OPTIONS:
                await message.reply_text(msg("reg_loyalty_invalid"), reply_markup=build_loyalty_keyboard())
                return
            reg.loyalty_status = text
            session.state = ConversationState.AWAIT_REG_BANK
            await message.reply_text(msg("reg_step_7"), reply_markup=build_bank_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_BANK:
            if text not in BANK_LABEL_TO_CODE:
                await message.reply_text(msg("reg_bank_invalid"), reply_markup=build_bank_keyboard())
                return
            reg.bank_status = BANK_LABEL_TO_CODE[text] or None
            session.state = ConversationState.AWAIT_REG_DESIRED_PRICE
            await message.reply_text(msg("reg_step_8"), reply_markup=build_numeric_edit_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_DESIRED_PRICE:
            desired_price = self._parse_decimal(text)
            if desired_price is None or desired_price <= 0:
                await message.reply_text(msg("reg_price_invalid"), reply_markup=build_numeric_edit_keyboard())
                return
            reg.desired_price_rub = desired_price
            await self._finish_registration(telegram_user_id, reg, message)
    async def _finish_registration(self, telegram_user_id: int, reg: RegistrationDraft, message) -> None:
        try:
            guest_id = self._adapter.register_guest_by_phone(
                telegram_user_id=telegram_user_id,
                phone=reg.phone or "",
                name=reg.name or "",
                adults=reg.adults or 1,
                children_4_13=reg.children_4_13 or 0,
                infants_0_3=reg.infants_0_3 or 0,
                allowed_groups=reg.allowed_groups or set(),
                loyalty_status=reg.loyalty_status or "White",
                bank_status=reg.bank_status,
                desired_price_rub=reg.desired_price_rub or Decimal("0"),
            )
        except Exception:
            logger.exception("registration_failed user_id=%s", telegram_user_id)
            await message.reply_text(msg("registration_failed"))
            self._sessions.reset(telegram_user_id)
            return

        self._sessions.reset(telegram_user_id)
        await self._send_main_menu_for_guest(message=message, guest_id=guest_id)

    async def _handle_edit_step(self, telegram_user_id: int, text: str, message) -> None:
        session = self._sessions.get(telegram_user_id)
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        if session.state == ConversationState.EDIT_MENU:
            if text == EDIT_ADULTS_BUTTON:
                session.state = ConversationState.EDIT_ADULTS
                await message.reply_text(msg("reg_step_2"), reply_markup=build_numeric_edit_keyboard())
                return
            if text == EDIT_CHILDREN_BUTTON:
                session.state = ConversationState.EDIT_CHILDREN_4_13
                await message.reply_text(msg("reg_step_3"), reply_markup=build_numeric_edit_keyboard())
                return
            if text == EDIT_INFANTS_BUTTON:
                session.state = ConversationState.EDIT_INFANTS_0_3
                await message.reply_text(msg("reg_step_4"), reply_markup=build_numeric_edit_keyboard())
                return
            if text == EDIT_GROUPS_BUTTON:
                session.state = ConversationState.EDIT_GROUPS
                profile = self._adapter.get_guest_profile(guest_id=guest_id)
                selected = profile.effective_allowed_groups if profile and profile.effective_allowed_groups else set()
                session.registration = RegistrationDraft(allowed_groups=set(selected))
                await message.reply_text(msg("reg_step_5"), reply_markup=build_categories_inline_keyboard(selected_codes=set(selected)))
                return
            if text == EDIT_LOYALTY_BUTTON:
                session.state = ConversationState.EDIT_LOYALTY
                await message.reply_text(msg("reg_step_6"), reply_markup=build_loyalty_keyboard())
                return
            if text == EDIT_BANK_BUTTON:
                session.state = ConversationState.EDIT_BANK
                await message.reply_text(msg("reg_step_7"), reply_markup=build_bank_keyboard())
                return
            if text == EDIT_PRICE_BUTTON:
                session.state = ConversationState.EDIT_DESIRED_PRICE
                await message.reply_text(msg("reg_step_8"), reply_markup=build_numeric_edit_keyboard())
                return
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_keyboard())
            return

        try:
            if session.state == ConversationState.EDIT_ADULTS:
                v = self._parse_int(text)
                if v is None or v < 1:
                    await message.reply_text(msg("reg_adults_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._adapter.update_guest_profile(guest_id=guest_id, adults=v)
            elif session.state == ConversationState.EDIT_CHILDREN_4_13:
                v = self._parse_int(text)
                if v is None or v < 0:
                    await message.reply_text(msg("reg_children_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._adapter.update_guest_profile(guest_id=guest_id, children_4_13=v)
            elif session.state == ConversationState.EDIT_INFANTS_0_3:
                v = self._parse_int(text)
                if v is None or v < 0:
                    await message.reply_text(msg("reg_infants_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._adapter.update_guest_profile(guest_id=guest_id, infants_0_3=v)
            elif session.state == ConversationState.EDIT_LOYALTY:
                if text not in LOYALTY_OPTIONS:
                    await message.reply_text(msg("reg_loyalty_invalid"), reply_markup=build_loyalty_keyboard())
                    return
                self._adapter.update_guest_profile(guest_id=guest_id, loyalty_status=text, bank_status="")
            elif session.state == ConversationState.EDIT_BANK:
                if text not in BANK_LABEL_TO_CODE:
                    await message.reply_text(msg("reg_bank_invalid"), reply_markup=build_bank_keyboard())
                    return
                self._adapter.update_guest_profile(guest_id=guest_id, bank_status=BANK_LABEL_TO_CODE[text])
            elif session.state == ConversationState.EDIT_DESIRED_PRICE:
                v = self._parse_decimal(text)
                if v is None or v <= 0:
                    await message.reply_text(msg("reg_price_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._adapter.update_guest_profile(guest_id=guest_id, desired_price_rub=v)
            else:
                return
        except Exception:
            logger.exception("edit_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await message.reply_text(msg("registration_failed"), reply_markup=build_edit_menu_keyboard())
            return

        session.state = ConversationState.EDIT_MENU
        await message.reply_text(msg("edit_saved"), reply_markup=build_edit_menu_keyboard())

    async def _handle_best_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            self._sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        group_id = data.split(":", 1)[1].strip().upper()
        try:
            picks = self._adapter.get_best_periods(guest_id=guest_id, group_id=group_id, top_k=3)
            response = render_best_periods(guest_id=guest_id, group_id=group_id, picks=picks)
        except Exception:
            logger.exception("best_period_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("best_period_failed"))
            self._sessions.reset(telegram_user_id)
            return

        await query.answer()
        if query.message is not None:
            await query.message.reply_text(response, reply_markup=build_best_period_details_inline_keyboard())

    async def _handle_quotes_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            self._sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        group_id = data.split(":", 1)[1].strip().upper()
        session = self._sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_QUOTES_CALENDAR
        session.period_quotes = PeriodQuotesDraft(
            group_id=group_id,
            month_cursor=first_day_of_month(date.today()),
            checkin=None,
            checkout=None,
        )
        await query.answer()
        await query.edit_message_text(
            text=msg("ask_quotes_calendar"),
            reply_markup=build_period_calendar_keyboard(
                month_cursor=session.period_quotes.month_cursor,
                checkin=session.period_quotes.checkin,
                checkout=session.period_quotes.checkout,
            ),
        )
    async def _handle_calendar_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = self._sessions.get(telegram_user_id)
        draft = session.period_quotes
        if session.state != ConversationState.AWAIT_QUOTES_CALENDAR or draft is None or draft.group_id is None or draft.month_cursor is None:
            await query.answer()
            return

        if data == "cal:noop":
            await query.answer()
            return

        if data.startswith("cal:nav:"):
            raw = data.split(":", 2)[2]
            try:
                draft.month_cursor = first_day_of_month(date.fromisoformat(raw))
            except ValueError:
                await query.answer()
                return
            await query.answer()
            await query.edit_message_reply_markup(
                reply_markup=build_period_calendar_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                )
            )
            return

        if not data.startswith("cal:day:"):
            await query.answer()
            return

        try:
            picked = date.fromisoformat(data.split(":", 2)[2])
        except ValueError:
            await query.answer()
            return

        if draft.checkin is None:
            draft.checkin = picked
            draft.checkout = None
            draft.month_cursor = first_day_of_month(picked)
            await query.answer()
            await query.edit_message_reply_markup(
                reply_markup=build_period_calendar_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                )
            )
            return

        if draft.checkout is None:
            if picked <= draft.checkin:
                draft.checkin = picked
                draft.month_cursor = first_day_of_month(picked)
                await query.answer()
                await query.edit_message_reply_markup(
                    reply_markup=build_period_calendar_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=None,
                    )
                )
                return

            draft.checkout = picked
            await query.answer()
            await self._finish_period_quotes_by_calendar(
                telegram_user_id=telegram_user_id,
                query=query,
                group_id=draft.group_id,
                period_start=draft.checkin,
                period_end=draft.checkout,
            )

    async def _finish_period_quotes_by_calendar(self, *, telegram_user_id: int, query, group_id: str, period_start: date, period_end: date) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            self._sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            run_id, quotes = self._adapter.get_period_quotes(
                guest_id=guest_id,
                period_start=period_start,
                period_end=period_end,
                group_ids={group_id},
            )
            last_room_dates_by_category: dict[str, list[date]] = {}
            for category_name in {q.category_name for q in quotes}:
                tariffs = {q.tariff for q in quotes if q.category_name == category_name}
                last_room_dates_by_category[category_name] = self._adapter.get_last_room_dates(
                    guest_id=guest_id,
                    category_name=category_name,
                    period_start=period_start,
                    period_end=period_end,
                    tariffs=tariffs,
                )
        except Exception:
            logger.exception("period_quotes_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            if query.message is not None:
                await query.message.reply_text(msg("period_quotes_failed"))
            self._sessions.reset(telegram_user_id)
            return

        session = self._sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None:
            draft = PeriodQuotesDraft()
            session.period_quotes = draft
        draft.group_id = group_id
        draft.checkin = period_start
        draft.checkout = period_end
        draft.run_id = run_id
        draft.quotes = quotes
        draft.last_room_dates_by_category = last_room_dates_by_category
        draft.category_names = sorted({q.category_name for q in quotes})
        session.state = ConversationState.AWAIT_QUOTES_CATEGORY

        if query.message is not None:
            if not draft.category_names:
                await query.message.reply_text(
                    f"Нет вариантов на период {period_start.isoformat()} - {period_end.isoformat()}.",
                    reply_markup=build_main_menu_keyboard(),
                )
                self._sessions.reset(telegram_user_id)
                return
            await query.edit_message_text(
                text="Выберите категорию:",
                reply_markup=build_quotes_categories_inline_keyboard(category_names=draft.category_names),
            )

    async def _handle_quotes_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = self._sessions.get(telegram_user_id)
        draft = session.period_quotes
        if session.state != ConversationState.AWAIT_QUOTES_CATEGORY or draft is None:
            await query.answer()
            return
        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            await query.answer()
            return

        selected_category = category_names[category_idx]
        quotes = [q for q in (draft.quotes or []) if q.category_name == selected_category]
        run_id = draft.run_id or ""
        checkin = draft.checkin.isoformat() if draft.checkin else ""
        checkout = draft.checkout.isoformat() if draft.checkout else ""
        last_room_dates_by_category = draft.last_room_dates_by_category or {}
        response = render_period_quotes(
            guest_id=guest_id,
            run_id=run_id,
            period_start=checkin,
            period_end=checkout,
            quotes=quotes,
            last_room_dates_by_category={selected_category: last_room_dates_by_category.get(selected_category, [])},
        )
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                response,
                reply_markup=build_quotes_category_details_inline_keyboard(),
            )

    async def _open_available_categories(self, telegram_user_id: int, message) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return
        categories = self._adapter.get_available_categories(guest_id=guest_id)
        session = self._sessions.get(telegram_user_id)
        session.available_category_names = categories
        session.available_category_rows = None
        if not categories:
            await message.reply_text(msg("available_none"), reply_markup=build_main_menu_keyboard())
            return
        await message.reply_text(msg("available_pick_category"), reply_markup=build_available_categories_inline_keyboard(category_names=categories))

    async def _handle_available_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = self._sessions.get(telegram_user_id)
        categories = session.available_category_names or []
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return
        if idx < 0 or idx >= len(categories):
            await query.answer()
            return
        category_name = categories[idx]
        _, rows = self._adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = self._build_available_periods(rows=rows)
        session.available_category_rows = rows
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                self._render_available_category_periods(category_name=category_name, periods=periods),
                reply_markup=build_available_periods_inline_keyboard(
                    category_idx=idx,
                    periods=[
                        (p.start, p.end, self._format_period_button_label(start=p.start, end=p.end, price_minor=p.min_new_price_minor))
                        for p in periods
                    ],
                ),
            )

    async def _handle_available_period_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = self._sessions.get(telegram_user_id)
        categories = session.available_category_names or []
        parts = data.split(":")
        if len(parts) != 3:
            await query.answer()
            return
        try:
            category_idx = int(parts[1])
            period_idx = int(parts[2])
        except ValueError:
            await query.answer()
            return
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        rows = session.available_category_rows or []
        if not rows:
            _, rows = self._adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = self._build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        period = periods[period_idx]
        last_room_dates = self._adapter.get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period.start,
            period_end=period.end,
            tariffs={r.tariff for r in period.rows},
        )
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                self._render_available_period_details(category_name=category_name, period=period, last_room_dates=last_room_dates),
                reply_markup=build_available_period_details_inline_keyboard(category_idx=category_idx),
            )

    async def _handle_categories_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = self._sessions.get(telegram_user_id)
        reg = session.registration
        if session.state not in {ConversationState.AWAIT_REG_GROUPS, ConversationState.EDIT_GROUPS} or reg is None:
            await query.answer()
            return

        action = data.split(":", 1)[1]
        if action == "done":
            selected = reg.allowed_groups or set()
            if not selected:
                await query.answer(msg("reg_select_at_least_one"), show_alert=False)
                return
            await query.answer()
            if session.state == ConversationState.AWAIT_REG_GROUPS:
                session.state = ConversationState.AWAIT_REG_LOYALTY
                if query.message is not None:
                    await query.message.reply_text(msg("reg_step_6"), reply_markup=build_loyalty_keyboard())
            else:
                guest_id = self._adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
                if guest_id:
                    self._adapter.update_guest_profile(guest_id=guest_id, allowed_groups=set(selected))
                session.state = ConversationState.EDIT_MENU
                if query.message is not None:
                    await query.message.reply_text(msg("edit_saved"), reply_markup=build_edit_menu_keyboard())
            return

        code = action.strip().upper()
        if code not in CATEGORY_LABEL_TO_CODE.values():
            await query.answer()
            return
        if reg.allowed_groups is None:
            reg.allowed_groups = set()
        if code in reg.allowed_groups:
            reg.allowed_groups.remove(code)
        else:
            reg.allowed_groups.add(code)

        await query.answer()
        await query.edit_message_reply_markup(reply_markup=build_categories_inline_keyboard(selected_codes=reg.allowed_groups))

    async def _send_main_menu_for_guest(self, *, message, guest_id: str) -> None:
        profile = self._adapter.get_guest_profile(guest_id=guest_id)
        if profile is None:
            await message.reply_text(msg("profile_not_found"), reply_markup=build_main_menu_keyboard())
            return
        await message.reply_text(self._render_profile(profile), reply_markup=build_main_menu_keyboard())

    def _render_profile(self, profile: GuestPreferences) -> str:
        code_to_label = {v: k for k, v in CATEGORY_LABEL_TO_CODE.items()}
        groups = sorted(profile.effective_allowed_groups or set())
        group_lines = [f" • {code_to_label.get(g, g)}" for g in groups] if groups else [" • —"]
        loyalty = profile.loyalty_status.value.capitalize() if profile.loyalty_status else "—"
        bank = profile.bank_status.value if profile.bank_status else "нет"
        desired = profile.desired_price_per_night.round_rubles()
        name = profile.guest_name or "Гость"
        return (
            "Ваши данные:\n"
            f" Имя: {name}\n"
            f" Взрослых: {profile.occupancy.adults}\n"
            f" Детей 4–17: {profile.occupancy.children_4_13}\n"
            f" Детей 0–3: {profile.occupancy.infants}\n"
            " Категории:\n"
            f"{chr(10).join(group_lines)}\n"
            f" Статус лояльности: {loyalty}\n"
            f" Статус в Сбере: {bank}\n"
            f" Желаемая цена: {desired} ₽"
        )

    def _render_available_category_periods(self, *, category_name: str, periods: list[AvailablePeriod]) -> str:
        if not periods:
            return f"{category_name}\n\nПериоды проживания:\nНет данных."
        return f"{category_name}\n\nПериоды проживания:"

    def _render_available_period_details(self, *, category_name: str, period: AvailablePeriod, last_room_dates: list[date]) -> str:
        lines = [
            category_name,
            f"{self._format_date(period.start)} - {self._format_date(period.end)}",
            "",
        ]

        rows_by_tariff: dict[str, MatchedDateRecord] = {}
        for row in period.rows:
            key = row.tariff.strip().lower()
            current = rows_by_tariff.get(key)
            if current is None or row.new_price_minor < current.new_price_minor:
                rows_by_tariff[key] = row

        for tariff_key in sorted(rows_by_tariff.keys()):
            row = rows_by_tariff[tariff_key]
            lines.extend(
                [
                    f'Тариф: "{self._tariff_label(row.tariff)}"',
                    f"Цена открытого рынка: {self._minor_to_rub(row.old_price_minor):.2f} рублей в сутки",
                    f"Ваша цена: {self._minor_to_rub(row.new_price_minor):.2f} рублей в сутки",
                    "",
                ]
            )

        offer_name = "—"
        offer_percent = "—"
        status_name = "—"
        status_percent = "—"
        for row in period.rows:
            if row.offer_title or row.offer_repr or row.offer_id:
                offer_name = row.offer_title or row.offer_id or "—"
                offer_percent = row.offer_repr or "—"
                break
        for row in period.rows:
            if row.bank_status and row.bank_percent is not None:
                status_name = f"сбер ({row.bank_status})"
                status_percent = self._format_percent(row.bank_percent)
                break
            if row.loyalty_status and row.loyalty_percent is not None:
                status_name = f"программа лояльности ({row.loyalty_status})"
                status_percent = self._format_percent(row.loyalty_percent)
                break

        lines.extend(
            [
                "Примененные скидки:",
                f'Специальное предложение: "{offer_name}", размер скидки {offer_percent}',
                f"Статус: {status_name}, размер скидки {status_percent}",
            ]
        )
        if last_room_dates:
            last_room_line = ", ".join(self._format_date(x) for x in sorted(set(last_room_dates)))
            lines.extend(["", f"Последние номера: {last_room_line}"])
        return "\n".join(lines).strip()

    @staticmethod
    def _build_available_periods(*, rows: list[MatchedDateRecord]) -> list[AvailablePeriod]:
        grouped: dict[tuple[date, date], list[MatchedDateRecord]] = {}
        for row in rows:
            start = row.date
            end = row.period_end or row.date
            grouped.setdefault((start, end), []).append(row)

        periods: list[AvailablePeriod] = []
        for (start, end), group_rows in grouped.items():
            min_new_price_minor = min(r.new_price_minor for r in group_rows)
            periods.append(
                AvailablePeriod(
                    start=start,
                    end=end,
                    min_new_price_minor=min_new_price_minor,
                    rows=sorted(group_rows, key=lambda r: (r.tariff, r.new_price_minor)),
                )
            )
        periods.sort(key=lambda p: (p.start, p.end, p.min_new_price_minor))
        return periods

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%d.%m.%y")

    @staticmethod
    def _minor_to_rub(value: int) -> float:
        return value / 100

    def _format_period_button_label(self, *, start: date, end: date, price_minor: int) -> str:
        return f"{self._format_date(start)} - {self._format_date(end)}, {self._minor_to_rub(price_minor):.2f} рублей в сутки"

    @staticmethod
    def _tariff_label(tariff: str) -> str:
        key = tariff.strip().lower()
        if key == "breakfast":
            return "Только завтраки"
        if key == "fullpansion":
            return "Только полный пансион"
        return tariff

    @staticmethod
    def _format_percent(value: Decimal) -> str:
        raw = f"{value * Decimal('100'):.2f}"
        trimmed = raw.rstrip("0").rstrip(".")
        return f"{trimmed}%"

    @staticmethod
    def _parse_int(value: str) -> int | None:
        try:
            return int(value.strip())
        except ValueError:
            return None

    @staticmethod
    def _parse_decimal(value: str) -> Decimal | None:
        raw = value.strip().replace(" ", "").replace(",", ".")
        try:
            return Decimal(raw)
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _telegram_profile_name(user) -> str:
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        username = (getattr(user, "username", None) or "").strip()
        full = f"{first} {last}".strip()
        if full:
            return full
        if username:
            return username
        return "Guest"
