from __future__ import annotations

import logging
from decimal import Decimal

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.main_menu import (
    AVAILABLE_ROOMS_BUTTON,
    BEST_PERIOD_BUTTON,
    EDIT_ADULTS_BUTTON,
    EDIT_DATA_BUTTON,
    EDIT_BANK_BUTTON,
    EDIT_CHILDREN_BUTTON,
    EDIT_GROUPS_BUTTON,
    EDIT_INFANTS_BUTTON,
    EDIT_LOYALTY_BUTTON,
    EDIT_PRICE_BUTTON,
    build_bank_keyboard,
    build_categories_inline_keyboard,
    build_edit_menu_keyboard,
    build_loyalty_keyboard,
    build_numeric_edit_keyboard,
    PERIOD_QUOTES_BUTTON,
    build_phone_request_keyboard,
)
from src.presentation.telegram.keyboards.registration import (
    REGISTRATION_LOYALTY_NO_STATUS_BUTTON,
    build_registration_bank_keyboard,
    build_registration_categories_inline_keyboard,
    build_registration_navigation_keyboard,
    build_registration_loyalty_keyboard,
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
                await message.reply_text(render_loyalty_invalid(), reply_markup=build_registration_loyalty_keyboard())
                return
            reg.loyalty_status = normalized
            session.state = ConversationState.AWAIT_REG_BANK
            await message.reply_text(render_bank_prompt(), reply_markup=build_registration_bank_keyboard())
            return

        if session.state == ConversationState.AWAIT_REG_BANK:
            if text not in BANK_LABEL_TO_CODE:
                await message.reply_text(render_bank_invalid(), reply_markup=build_registration_bank_keyboard())
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

    async def handle_edit_step(self, telegram_user_id: int, text: str, message) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
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
                profile = self._deps.adapter.get_guest_profile(guest_id=guest_id)
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
                v = parse_int(text)
                if v is None or v < 1:
                    await message.reply_text(msg("reg_adults_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._deps.adapter.update_guest_profile(guest_id=guest_id, adults=v)
            elif session.state == ConversationState.EDIT_CHILDREN_4_13:
                v = parse_int(text)
                if v is None or v < 0:
                    await message.reply_text(msg("reg_children_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._deps.adapter.update_guest_profile(guest_id=guest_id, children_4_13=v)
            elif session.state == ConversationState.EDIT_INFANTS_0_3:
                v = parse_int(text)
                if v is None or v < 0:
                    await message.reply_text(msg("reg_infants_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._deps.adapter.update_guest_profile(guest_id=guest_id, infants_0_3=v)
            elif session.state == ConversationState.EDIT_LOYALTY:
                if text not in LOYALTY_OPTIONS:
                    await message.reply_text(msg("reg_loyalty_invalid"), reply_markup=build_loyalty_keyboard())
                    return
                self._deps.adapter.update_guest_profile(guest_id=guest_id, loyalty_status=text, bank_status="")
            elif session.state == ConversationState.EDIT_BANK:
                if text not in BANK_LABEL_TO_CODE:
                    await message.reply_text(msg("reg_bank_invalid"), reply_markup=build_bank_keyboard())
                    return
                self._deps.adapter.update_guest_profile(guest_id=guest_id, bank_status=BANK_LABEL_TO_CODE[text])
            elif session.state == ConversationState.EDIT_DESIRED_PRICE:
                v = parse_decimal(text)
                if v is None or v <= 0:
                    await message.reply_text(msg("reg_price_invalid"), reply_markup=build_numeric_edit_keyboard())
                    return
                self._deps.adapter.update_guest_profile(guest_id=guest_id, desired_price_rub=v)
            else:
                return
        except Exception:
            logger.exception("edit_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await message.reply_text(msg("registration_failed"), reply_markup=build_edit_menu_keyboard())
            return

        session.state = ConversationState.EDIT_MENU
        await message.reply_text(msg("edit_saved"), reply_markup=build_edit_menu_keyboard())

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

            await query.answer()
            if session.state == ConversationState.AWAIT_REG_GROUPS:
                session.state = ConversationState.AWAIT_REG_LOYALTY
                if query.message is not None:
                    await query.message.reply_text(render_loyalty_prompt(), reply_markup=build_registration_loyalty_keyboard())
            else:
                guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
                if guest_id:
                    self._deps.adapter.update_guest_profile(guest_id=guest_id, allowed_groups=set(selected))
                session.state = ConversationState.EDIT_MENU
                if query.message is not None:
                    await query.message.reply_text(msg("edit_saved"), reply_markup=build_edit_menu_keyboard())
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

        await query.edit_message_reply_markup(reply_markup=build_categories_inline_keyboard(selected_codes=reg.allowed_groups))

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
            await message.reply_text(render_loyalty_prompt(), reply_markup=build_registration_loyalty_keyboard())
            return True
        if session.state == ConversationState.AWAIT_REG_DESIRED_PRICE:
            session.state = ConversationState.AWAIT_REG_BANK
            await message.reply_text(render_bank_prompt(), reply_markup=build_registration_bank_keyboard())
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
            await message.reply_text(msg("edit_pick_field"), reply_markup=build_edit_menu_keyboard())
            return True

        if session.state == ConversationState.EDIT_MENU and guest_id:
            await self._deps.sessions.reset(telegram_user_id)
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            return True
        return False

    async def _finish_registration(self, telegram_user_id: int, reg: RegistrationDraft, message) -> None:
        try:
            guest_id = self._deps.adapter.register_guest_by_phone(
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
            return build_registration_loyalty_keyboard()
        if state == ConversationState.AWAIT_REG_BANK:
            return build_registration_bank_keyboard()
        if state == ConversationState.AWAIT_REG_GROUPS:
            return build_registration_navigation_keyboard()
        return build_registration_navigation_keyboard()


def _normalize_loyalty_selection(value: str) -> str:
    text = value.strip()
    if text == REGISTRATION_LOYALTY_NO_STATUS_BUTTON:
        return "White"
    return text
