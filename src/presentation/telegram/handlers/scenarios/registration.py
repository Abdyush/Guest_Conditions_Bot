from __future__ import annotations

import logging
from decimal import Decimal

from src.presentation.telegram.callbacks.data_parser import (
    PREFIX_EDIT_BANK,
    PREFIX_EDIT_FIELD,
    PREFIX_EDIT_LOYALTY,
    PREFIX_EDIT_NAV,
    PREFIX_REGISTRATION_BANK,
    PREFIX_REGISTRATION_LOYALTY,
)
from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.edit_profile import (
    build_edit_bank_inline_keyboard,
    build_edit_categories_inline_keyboard,
    build_edit_loyalty_inline_keyboard,
    build_edit_menu_inline_keyboard,
    build_edit_numeric_inline_keyboard,
    build_edit_profile_reply_keyboard,
)
from src.presentation.telegram.keyboards.main_menu import (
    AVAILABLE_ROOMS_BUTTON,
    BEST_PERIOD_BUTTON,
    EDIT_DATA_BUTTON,
    PERIOD_QUOTES_BUTTON,
    build_phone_request_keyboard,
)
from src.presentation.telegram.keyboards.registration import (
    REGISTRATION_LOYALTY_NO_STATUS_BUTTON,
    build_registration_bank_inline_keyboard,
    build_registration_categories_inline_keyboard,
    build_registration_loyalty_inline_keyboard,
    build_registration_navigation_keyboard,
    build_registration_numeric_keyboard,
)
from src.presentation.telegram.mappers.value_parser import parse_decimal, parse_int
from src.presentation.telegram.presenters.registration_presenter import (
    render_adults_invalid,
    render_adults_prompt,
    render_bank_invalid,
    render_bank_prompt,
    render_categories_prompt,
    render_children_invalid,
    render_children_prompt,
    render_groups_use_buttons,
    render_infants_invalid,
    render_infants_prompt,
    render_loyalty_invalid,
    render_loyalty_prompt,
    render_phone_reminder,
    render_price_invalid,
    render_price_prompt,
    render_registration_done,
    render_registration_flow_hint,
    render_select_at_least_one,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import RegistrationDraft
from src.presentation.telegram.ui_texts import BANK_LABEL_TO_CODE, CATEGORY_LABEL_TO_CODE, LOYALTY_OPTIONS, msg


logger = logging.getLogger(__name__)


class RegistrationScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.REGISTRATION)

    async def handle_flow_text(self, telegram_user_id: int, text: str, message) -> bool:
        if not await self.is_active(telegram_user_id):
            return False
        if text not in {
            EDIT_DATA_BUTTON,
            AVAILABLE_ROOMS_BUTTON,
            PERIOD_QUOTES_BUTTON,
            BEST_PERIOD_BUTTON,
        }:
            return False
        session = await self._deps.sessions.get(telegram_user_id)
        await message.reply_text(
            render_registration_flow_hint(),
            reply_markup=self._reply_markup_for_state(session.state),
        )
        return True

    async def handle_registration_step(self, telegram_user_id: int, text: str, message) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        reg = session.registration
        if reg is None:
            await self._deps.flow_guard.leave(telegram_user_id)
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(render_phone_reminder(), reply_markup=build_phone_request_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_ADULTS:
            adults = parse_int(text)
            if adults is None or adults < 1:
                await message.reply_text(render_adults_invalid(), reply_markup=build_registration_numeric_keyboard())
                return
            reg.adults = adults
            session.state = ConversationState.AWAIT_REG_CHILDREN_4_13
            await message.reply_text(render_children_prompt(), reply_markup=build_registration_numeric_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_CHILDREN_4_13:
            children = parse_int(text)
            if children is None or children < 0:
                await message.reply_text(render_children_invalid(), reply_markup=build_registration_numeric_keyboard())
                return
            reg.children_4_13 = children
            session.state = ConversationState.AWAIT_REG_INFANTS_0_3
            await message.reply_text(render_infants_prompt(), reply_markup=build_registration_numeric_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_INFANTS_0_3:
            infants = parse_int(text)
            if infants is None or infants < 0:
                await message.reply_text(render_infants_invalid(), reply_markup=build_registration_numeric_keyboard())
                return
            reg.infants_0_3 = infants
            session.state = ConversationState.AWAIT_REG_GROUPS
            await message.reply_text(
                render_categories_prompt(selected_codes=reg.allowed_groups or set()),
                reply_markup=build_registration_categories_inline_keyboard(selected_codes=reg.allowed_groups or set()),
            )
            return

        if session.state == ConversationState.AWAIT_REG_GROUPS:
            await message.reply_text(render_groups_use_buttons())
            return

        if session.state == ConversationState.AWAIT_REG_LOYALTY:
            normalized = _normalize_loyalty_selection(text)
            if normalized not in LOYALTY_OPTIONS:
                await self._show_registration_loyalty_prompt(message, text=render_loyalty_invalid())
                return
            reg.loyalty_status = normalized
            session.state = ConversationState.AWAIT_REG_BANK
            await self._show_registration_bank_prompt(message)
            return

        if session.state == ConversationState.AWAIT_REG_BANK:
            if text not in BANK_LABEL_TO_CODE:
                await self._show_registration_bank_prompt(message, text=render_bank_invalid())
                return
            reg.bank_status = BANK_LABEL_TO_CODE[text] or None
            session.state = ConversationState.AWAIT_REG_DESIRED_PRICE
            await message.reply_text(render_price_prompt(), reply_markup=build_registration_numeric_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_DESIRED_PRICE:
            desired_price = parse_decimal(text)
            if desired_price is None or desired_price <= 0:
                await message.reply_text(render_price_invalid(), reply_markup=build_registration_numeric_keyboard())
                return
            reg.desired_price_rub = desired_price
            await self._finish_registration(telegram_user_id, reg, message)

    async def open_edit_menu(self, telegram_user_id: int, message) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return
        session.state = ConversationState.EDIT_MENU
        await message.reply_text(reply_markup=build_edit_profile_reply_keyboard(), text=msg("edit_pick_field"))
        await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())

    async def handle_edit_step(self, telegram_user_id: int, text: str, message) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        if session.state == ConversationState.EDIT_MENU:
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())
            return

        try:
            if session.state == ConversationState.EDIT_ADULTS:
                v = parse_int(text)
                if v is None or v < 1:
                    await message.reply_text(msg("reg_adults_invalid"), reply_markup=build_edit_numeric_inline_keyboard())
                    return
                self._deps.profile.update_guest_profile(guest_id=guest_id, adults=v)
            elif session.state == ConversationState.EDIT_CHILDREN_4_13:
                v = parse_int(text)
                if v is None or v < 0:
                    await message.reply_text(msg("reg_children_invalid"), reply_markup=build_edit_numeric_inline_keyboard())
                    return
                self._deps.profile.update_guest_profile(guest_id=guest_id, children_4_13=v)
            elif session.state == ConversationState.EDIT_INFANTS_0_3:
                v = parse_int(text)
                if v is None or v < 0:
                    await message.reply_text(msg("reg_infants_invalid"), reply_markup=build_edit_numeric_inline_keyboard())
                    return
                self._deps.profile.update_guest_profile(guest_id=guest_id, infants_0_3=v)
            elif session.state == ConversationState.EDIT_LOYALTY:
                await message.reply_text(msg("reg_loyalty_invalid"), reply_markup=build_edit_loyalty_inline_keyboard())
                return
            elif session.state == ConversationState.EDIT_BANK:
                await message.reply_text(msg("reg_bank_invalid"), reply_markup=build_edit_bank_inline_keyboard())
                return
            elif session.state == ConversationState.EDIT_DESIRED_PRICE:
                v = parse_decimal(text)
                if v is None or v <= 0:
                    await message.reply_text(msg("reg_price_invalid"), reply_markup=build_edit_numeric_inline_keyboard())
                    return
                self._deps.profile.update_guest_profile(guest_id=guest_id, desired_price_rub=v)
            else:
                return
        except Exception:
            logger.exception("edit_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await message.reply_text(msg("registration_failed"), reply_markup=build_edit_profile_reply_keyboard())
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())
            return

        session.state = ConversationState.EDIT_MENU
        await message.reply_text(msg("edit_saved"), reply_markup=build_edit_profile_reply_keyboard())
        await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())

    async def handle_edit_field_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        action = data.removeprefix(PREFIX_EDIT_FIELD)
        if action == "back":
            await query.answer()
            if query.message is not None:
                await self._deps.sessions.reset(telegram_user_id)
                await send_main_menu_for_guest(deps=self._deps, message=query.message, guest_id=guest_id)
            return

        if action == "adults":
            session.state = ConversationState.EDIT_ADULTS
            prompt = msg("reg_step_2")
            markup = build_edit_numeric_inline_keyboard()
        elif action == "children":
            session.state = ConversationState.EDIT_CHILDREN_4_13
            prompt = msg("reg_step_3")
            markup = build_edit_numeric_inline_keyboard()
        elif action == "infants":
            session.state = ConversationState.EDIT_INFANTS_0_3
            prompt = msg("reg_step_4")
            markup = build_edit_numeric_inline_keyboard()
        elif action == "groups":
            session.state = ConversationState.EDIT_GROUPS
            profile = self._deps.profile.get_guest_profile(guest_id=guest_id)
            selected = profile.effective_allowed_groups if profile and profile.effective_allowed_groups else set()
            session.registration = RegistrationDraft(allowed_groups=set(selected))
            prompt = msg("reg_step_5")
            markup = build_edit_categories_inline_keyboard(selected_codes=set(selected))
        elif action == "loyalty":
            session.state = ConversationState.EDIT_LOYALTY
            prompt = msg("reg_step_6")
            markup = build_edit_loyalty_inline_keyboard()
        elif action == "bank":
            session.state = ConversationState.EDIT_BANK
            prompt = msg("reg_step_7")
            markup = build_edit_bank_inline_keyboard()
        elif action == "price":
            session.state = ConversationState.EDIT_DESIRED_PRICE
            prompt = msg("reg_step_8")
            markup = build_edit_numeric_inline_keyboard()
        else:
            await query.answer()
            return

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(prompt, reply_markup=markup)

    async def handle_edit_loyalty_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        value = data.removeprefix(PREFIX_EDIT_LOYALTY)
        if value not in LOYALTY_OPTIONS:
            await query.answer()
            return

        try:
            self._deps.profile.update_guest_profile(guest_id=guest_id, loyalty_status=value, bank_status="")
        except Exception:
            logger.exception("edit_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("registration_failed"), reply_markup=build_edit_profile_reply_keyboard())
                await query.message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())
            return
        session.state = ConversationState.EDIT_MENU
        await query.answer(msg("edit_saved"), show_alert=False)
        if query.message is not None:
            await query.edit_message_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())

    async def handle_edit_bank_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        value = data.removeprefix(PREFIX_EDIT_BANK)
        if value != "none" and value not in BANK_LABEL_TO_CODE.values():
            await query.answer()
            return

        try:
            self._deps.profile.update_guest_profile(
                guest_id=guest_id,
                bank_status="" if value == "none" else value,
            )
        except Exception:
            logger.exception("edit_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("registration_failed"), reply_markup=build_edit_profile_reply_keyboard())
                await query.message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())
            return
        session.state = ConversationState.EDIT_MENU
        await query.answer(msg("edit_saved"), show_alert=False)
        if query.message is not None:
            await query.edit_message_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())

    async def handle_edit_navigation_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        if data != f"{PREFIX_EDIT_NAV}back":
            await query.answer()
            return
        session.state = ConversationState.EDIT_MENU
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())

    async def handle_categories_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        reg = session.registration
        if session.state not in {ConversationState.AWAIT_REG_GROUPS, ConversationState.EDIT_GROUPS} or reg is None:
            await query.answer()
            return

        action = data.split(":", 1)[1]
        if action == "done":
            selected = reg.allowed_groups or set()
            if not selected:
                if session.state == ConversationState.AWAIT_REG_GROUPS and query.message is not None:
                    await query.answer()
                    await query.edit_message_text(
                        render_select_at_least_one(),
                        reply_markup=build_registration_categories_inline_keyboard(selected_codes=selected),
                    )
                else:
                    await query.answer(msg("reg_select_at_least_one"), show_alert=False)
                return

            if session.state == ConversationState.AWAIT_REG_GROUPS:
                await query.answer()
                session.state = ConversationState.AWAIT_REG_LOYALTY
                if query.message is not None:
                    await self._show_registration_loyalty_prompt(query.message)
            else:
                guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
                if guest_id:
                    self._deps.profile.update_guest_profile(guest_id=guest_id, allowed_groups=set(selected))
                session.state = ConversationState.EDIT_MENU
                await query.answer(msg("edit_saved"), show_alert=False)
                if query.message is not None:
                    await query.edit_message_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())
            return

        if action == "all" and session.state == ConversationState.AWAIT_REG_GROUPS:
            all_codes = set(CATEGORY_LABEL_TO_CODE.values())
            reg.allowed_groups = set() if (reg.allowed_groups or set()) == all_codes else set(all_codes)
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(
                    render_categories_prompt(selected_codes=reg.allowed_groups),
                    reply_markup=build_registration_categories_inline_keyboard(selected_codes=reg.allowed_groups),
                )
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
        if session.state == ConversationState.AWAIT_REG_GROUPS and query.message is not None:
            await query.edit_message_text(
                render_categories_prompt(selected_codes=reg.allowed_groups),
                reply_markup=build_registration_categories_inline_keyboard(selected_codes=reg.allowed_groups),
            )
            return

        await query.edit_message_reply_markup(reply_markup=build_edit_categories_inline_keyboard(selected_codes=reg.allowed_groups))

    async def handle_registration_loyalty_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        reg = session.registration
        if session.state != ConversationState.AWAIT_REG_LOYALTY or reg is None:
            await query.answer()
            return

        value = data.removeprefix(PREFIX_REGISTRATION_LOYALTY)
        if value not in LOYALTY_OPTIONS:
            await query.answer()
            return

        reg.loyalty_status = value
        session.state = ConversationState.AWAIT_REG_BANK
        await query.answer()
        if query.message is not None:
            await query.edit_message_reply_markup(reply_markup=None)
            await self._show_registration_bank_prompt(query.message)

    async def handle_registration_bank_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        reg = session.registration
        if session.state != ConversationState.AWAIT_REG_BANK or reg is None:
            await query.answer()
            return

        value = data.removeprefix(PREFIX_REGISTRATION_BANK)
        if value != "none" and value not in BANK_LABEL_TO_CODE.values():
            await query.answer()
            return

        reg.bank_status = None if value == "none" else value
        session.state = ConversationState.AWAIT_REG_DESIRED_PRICE
        await query.answer()
        if query.message is not None:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(render_price_prompt(), reply_markup=build_registration_numeric_keyboard())

    async def handle_back(self, telegram_user_id: int, message, guest_id: str | None) -> bool:
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state == ConversationState.AWAIT_REG_CHILDREN_4_13:
            session.state = ConversationState.AWAIT_REG_ADULTS
            await message.reply_text(render_adults_prompt(), reply_markup=build_registration_numeric_keyboard())
            return True
        if session.state == ConversationState.AWAIT_REG_INFANTS_0_3:
            session.state = ConversationState.AWAIT_REG_CHILDREN_4_13
            await message.reply_text(render_children_prompt(), reply_markup=build_registration_numeric_keyboard())
            return True
        if session.state == ConversationState.AWAIT_REG_GROUPS:
            session.state = ConversationState.AWAIT_REG_INFANTS_0_3
            await message.reply_text(render_infants_prompt(), reply_markup=build_registration_numeric_keyboard())
            return True
        if session.state == ConversationState.AWAIT_REG_LOYALTY:
            session.state = ConversationState.AWAIT_REG_GROUPS
            reg = session.registration
            selected = reg.allowed_groups if reg and reg.allowed_groups else set()
            await message.reply_text(
                render_categories_prompt(selected_codes=selected),
                reply_markup=build_registration_categories_inline_keyboard(selected_codes=selected),
            )
            return True
        if session.state == ConversationState.AWAIT_REG_BANK:
            session.state = ConversationState.AWAIT_REG_LOYALTY
            await self._show_registration_loyalty_prompt(message)
            return True
        if session.state == ConversationState.AWAIT_REG_DESIRED_PRICE:
            session.state = ConversationState.AWAIT_REG_BANK
            await self._show_registration_bank_prompt(message)
            return True
        if session.state == ConversationState.AWAIT_REG_ADULTS:
            await self._deps.flow_guard.leave(telegram_user_id)
            session.state = ConversationState.AWAIT_PHONE_CONTACT
            session.registration = None
            await message.reply_text(render_phone_reminder(), reply_markup=build_phone_request_keyboard())
            return True

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
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_inline_keyboard())
            return True

        if session.state == ConversationState.EDIT_MENU and guest_id:
            await self._deps.sessions.reset(telegram_user_id)
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            return True
        return False

    async def _finish_registration(self, telegram_user_id: int, reg: RegistrationDraft, message) -> None:
        try:
            guest_id = self._deps.profile.register_guest_by_phone(
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
            await self._deps.sessions.reset(telegram_user_id)
            return

        await self._deps.sessions.reset(telegram_user_id)
        await message.reply_text(render_registration_done())
        await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)

    @staticmethod
    def _reply_markup_for_state(state: ConversationState):
        if state in {
            ConversationState.AWAIT_REG_ADULTS,
            ConversationState.AWAIT_REG_CHILDREN_4_13,
            ConversationState.AWAIT_REG_INFANTS_0_3,
            ConversationState.AWAIT_REG_DESIRED_PRICE,
        }:
            return build_registration_numeric_keyboard()
        if state == ConversationState.AWAIT_REG_LOYALTY:
            return build_registration_navigation_keyboard()
        if state == ConversationState.AWAIT_REG_BANK:
            return build_registration_navigation_keyboard()
        if state == ConversationState.AWAIT_REG_GROUPS:
            return build_registration_navigation_keyboard()
        return build_registration_navigation_keyboard()

    @staticmethod
    async def _show_registration_loyalty_prompt(message, *, text: str | None = None) -> None:
        prompt = text or render_loyalty_prompt()
        await message.reply_text(prompt, reply_markup=build_registration_loyalty_inline_keyboard())

    @staticmethod
    async def _show_registration_bank_prompt(message, *, text: str | None = None) -> None:
        prompt = text or render_bank_prompt()
        await message.reply_text(prompt, reply_markup=build_registration_bank_inline_keyboard())


def _normalize_loyalty_selection(value: str) -> str:
    text = value.strip()
    if text == REGISTRATION_LOYALTY_NO_STATUS_BUTTON:
        return "White"
    return text

