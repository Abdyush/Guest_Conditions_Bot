from __future__ import annotations

import logging

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.best_periods import (
    build_best_categories_inline_keyboard,
    build_best_groups_inline_keyboard,
    build_best_offer_text_inline_keyboard,
    build_best_period_result_inline_keyboard,
    build_best_periods_scenario_keyboard,
)
from src.presentation.telegram.keyboards.main_menu import BEST_PERIOD_BUTTON, build_phone_request_keyboard
from src.presentation.telegram.presenters.best_periods_presenter import (
    render_best_categories_prompt,
    render_best_groups_prompt,
    render_best_offer_text,
    render_best_period_card,
    render_best_period_empty,
    render_best_period_flow_hint,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import BestPeriodDraft
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)


class BestPeriodsScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def open_group_picker(self, *, telegram_user_id: int, message) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_BEST_GROUP_ID
        session.best_period = None
        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.BEST_PERIODS)
        await message.reply_text(
            "Сценарий «Самый выгодный период» открыт. Для выхода используйте кнопку «Главное меню» ниже.",
            reply_markup=build_best_periods_scenario_keyboard(),
        )
        await message.reply_text(
            render_best_groups_prompt(),
            reply_markup=build_best_groups_inline_keyboard(),
        )

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.BEST_PERIODS)

    async def handle_flow_text(self, telegram_user_id: int, text: str, message) -> bool:
        if not await self.is_active(telegram_user_id):
            return False
        if text == BEST_PERIOD_BUTTON:
            await self.open_group_picker(telegram_user_id=telegram_user_id, message=message)
            return True
        await message.reply_text(
            render_best_period_flow_hint(),
            reply_markup=build_best_periods_scenario_keyboard(),
        )
        return True

    async def handle_best_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        group_id = data.split(":", 1)[1].strip().upper()
        try:
            category_names = self._deps.adapter.get_best_period_categories(guest_id=guest_id, group_id=group_id)
        except Exception:
            logger.exception("best_period_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("best_period_failed"), reply_markup=build_best_periods_scenario_keyboard())
            await self._deps.sessions.reset(telegram_user_id)
            return

        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_BEST_CATEGORY_ID
        session.best_period = BestPeriodDraft(group_id=group_id, category_names=category_names)

        await query.answer()
        if query.message is not None:
            if not category_names:
                await query.edit_message_text(
                    msg("best_period_failed"),
                    reply_markup=build_best_groups_inline_keyboard(),
                )
                return
            await query.edit_message_text(
                render_best_categories_prompt(),
                reply_markup=build_best_categories_inline_keyboard(category_names=category_names),
            )

    async def handle_best_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.best_period
        if session.state != ConversationState.AWAIT_BEST_CATEGORY_ID or draft is None or draft.group_id is None:
            await query.answer()
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        await self._show_best_period_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            category_idx=category_idx,
        )

    async def handle_best_offer_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        result = await self._resolve_best_period_result(guest_id=guest_id, telegram_user_id=telegram_user_id, category_idx=category_idx)
        if result is None:
            await query.answer()
            return
        _, best_pick, quotes = result

        row_with_offer = next((quote for quote in quotes if quote.offer_id or quote.offer_title), None)
        if row_with_offer is None:
            await query.answer("Текст специального предложения не найден.", show_alert=False)
            return

        offer_text = self._deps.adapter.get_offer_text(
            offer_id=row_with_offer.offer_id,
            offer_title=row_with_offer.offer_title,
        )
        if not offer_text:
            offer_text = "Текст специального предложения недоступен."

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_best_offer_text(offer_title=row_with_offer.offer_title, offer_text=offer_text),
                reply_markup=build_best_offer_text_inline_keyboard(category_idx=category_idx),
            )

    async def handle_best_result_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        await self._show_best_period_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            category_idx=category_idx,
        )

    async def handle_nav_back_groups(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_BEST_GROUP_ID
        session.best_period = None
        if query.message is not None:
            await query.edit_message_text(
                render_best_groups_prompt(),
                reply_markup=build_best_groups_inline_keyboard(),
            )

    async def handle_nav_back_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.best_period
        if draft is None:
            return
        session.state = ConversationState.AWAIT_BEST_CATEGORY_ID
        if query.message is not None:
            await query.edit_message_text(
                render_best_categories_prompt(),
                reply_markup=build_best_categories_inline_keyboard(category_names=draft.category_names or []),
            )

    async def handle_back(self, telegram_user_id: int, message, guest_id: str) -> bool:
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state == ConversationState.AWAIT_BEST_CATEGORY_ID:
            session.state = ConversationState.AWAIT_BEST_GROUP_ID
            session.best_period = None
            await message.reply_text(
                render_best_groups_prompt(),
                reply_markup=build_best_groups_inline_keyboard(),
            )
            return True
        if session.state == ConversationState.AWAIT_BEST_GROUP_ID:
            await self._deps.sessions.reset(telegram_user_id)
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            return True
        return False

    async def _show_best_period_result(self, *, guest_id: str, telegram_user_id: int, query, category_idx: int) -> None:
        result = await self._resolve_best_period_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            category_idx=category_idx,
        )
        if result is None:
            await query.answer()
            return

        category_name, best_pick, quotes = result
        last_room_dates = self._deps.adapter.get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=best_pick.start_date,
            period_end=best_pick.end_date_inclusive,
            tariffs={quote.tariff for quote in quotes} if quotes else {best_pick.tariff_code},
        )
        has_offer_text = any((quote.offer_id or quote.offer_title) for quote in quotes)

        await query.answer()
        if query.message is not None:
            if not quotes:
                await query.edit_message_text(
                    render_best_period_empty(category_name=category_name),
                    reply_markup=build_best_categories_inline_keyboard(
                        category_names=(await self._deps.sessions.get(telegram_user_id)).best_period.category_names or []
                    ),
                )
                return
            await query.edit_message_text(
                render_best_period_card(
                    category_name=category_name,
                    best_pick=best_pick,
                    quotes=quotes,
                    last_room_dates=last_room_dates,
                ),
                reply_markup=build_best_period_result_inline_keyboard(
                    category_idx=category_idx,
                    has_offer_text=has_offer_text,
                ),
            )

    async def _resolve_best_period_result(
        self,
        *,
        guest_id: str,
        telegram_user_id: int,
        category_idx: int,
    ) -> tuple[str, object, list] | None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.best_period
        if draft is None or draft.group_id is None:
            return None

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            return None

        category_name = category_names[category_idx]
        try:
            best_pick, quotes = self._deps.adapter.get_best_period_details_for_category(
                guest_id=guest_id,
                group_id=draft.group_id,
                category_name=category_name,
            )
        except Exception:
            logger.exception("best_period_failed user_id=%s guest_id=%s category=%s", telegram_user_id, guest_id, category_name)
            return None
        if best_pick is None:
            return None
        return category_name, best_pick, quotes
