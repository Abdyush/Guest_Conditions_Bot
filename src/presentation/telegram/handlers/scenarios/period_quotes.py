from __future__ import annotations

import logging
from datetime import date

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.main_menu import PERIOD_QUOTES_BUTTON, build_phone_request_keyboard
from src.presentation.telegram.keyboards.period_quotes import (
    build_period_quotes_calendar_inline_keyboard,
    build_period_quotes_categories_inline_keyboard,
    build_period_quotes_empty_inline_keyboard,
    build_period_quotes_groups_inline_keyboard,
    build_period_quotes_offer_text_inline_keyboard,
    build_period_quotes_result_inline_keyboard,
    build_period_quotes_scenario_keyboard,
)
from src.presentation.telegram.presenters.period_quotes_presenter import (
    render_period_quote_card,
    render_period_quote_offer_text,
    render_period_quotes_calendar_prompt,
    render_period_quotes_category_prompt,
    render_period_quotes_empty,
    render_period_quotes_flow_hint,
    render_period_quotes_groups_prompt,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import PeriodQuotesDraft
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)


class PeriodQuotesScenario:
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
        session.state = ConversationState.AWAIT_QUOTES_GROUP
        session.period_quotes = None
        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.PERIOD_QUOTES)
        await message.reply_text(
            "Сценарий «Цены на период» открыт. Для выхода используйте кнопку «Главное меню» ниже.",
            reply_markup=build_period_quotes_scenario_keyboard(),
        )
        await message.reply_text(
            render_period_quotes_groups_prompt(),
            reply_markup=build_period_quotes_groups_inline_keyboard(),
        )

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.PERIOD_QUOTES)

    async def handle_flow_text(self, telegram_user_id: int, text: str, message) -> bool:
        if not await self.is_active(telegram_user_id):
            return False
        if text == PERIOD_QUOTES_BUTTON:
            await self.open_group_picker(telegram_user_id=telegram_user_id, message=message)
            return True
        await message.reply_text(
            render_period_quotes_flow_hint(),
            reply_markup=build_period_quotes_scenario_keyboard(),
        )
        return True

    async def handle_quotes_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        group_id = data.split(":", 1)[1].strip().upper()
        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_QUOTES_CALENDAR
        session.period_quotes = PeriodQuotesDraft(
            group_id=group_id,
            month_cursor=date.today().replace(day=1),
            checkin=None,
            checkout=None,
        )
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                text=render_period_quotes_calendar_prompt(),
                reply_markup=build_period_quotes_calendar_inline_keyboard(
                    month_cursor=session.period_quotes.month_cursor,
                    checkin=session.period_quotes.checkin,
                    checkout=session.period_quotes.checkout,
                ),
            )

    async def handle_calendar_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
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
                draft.month_cursor = date.fromisoformat(raw).replace(day=1)
            except ValueError:
                await query.answer()
                return
            await query.answer()
            await query.edit_message_reply_markup(
                reply_markup=build_period_quotes_calendar_inline_keyboard(
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
            draft.month_cursor = picked.replace(day=1)
            await query.answer()
            await query.edit_message_reply_markup(
                reply_markup=build_period_quotes_calendar_inline_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                )
            )
            return

        if draft.checkout is None:
            if picked <= draft.checkin:
                draft.checkin = picked
                draft.month_cursor = picked.replace(day=1)
                await query.answer()
                await query.edit_message_reply_markup(
                    reply_markup=build_period_quotes_calendar_inline_keyboard(
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

    async def handle_quotes_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if session.state != ConversationState.AWAIT_QUOTES_CATEGORY or draft is None:
            await query.answer()
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        await self._show_category_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            category_idx=category_idx,
        )

    async def handle_quotes_offer_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None:
            await query.answer()
            return

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            await query.answer()
            return

        category_name = category_names[category_idx]
        quotes = [item for item in (draft.quotes or []) if item.category_name == category_name]
        row_with_offer = next((item for item in quotes if item.offer_id or item.offer_title), None)
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
                render_period_quote_offer_text(
                    offer_title=row_with_offer.offer_title,
                    offer_text=offer_text,
                ),
                reply_markup=build_period_quotes_offer_text_inline_keyboard(category_idx=category_idx),
            )

    async def handle_quotes_result_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        await self._show_category_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            category_idx=category_idx,
        )

    async def handle_nav_back_group(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_QUOTES_GROUP
        session.period_quotes = None
        if query.message is not None:
            await query.edit_message_text(
                render_period_quotes_groups_prompt(),
                reply_markup=build_period_quotes_groups_inline_keyboard(),
            )

    async def handle_nav_back_calendar(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.month_cursor is None:
            return
        session.state = ConversationState.AWAIT_QUOTES_CALENDAR
        if query.message is not None:
            await query.edit_message_text(
                text=render_period_quotes_calendar_prompt(),
                reply_markup=build_period_quotes_calendar_inline_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                ),
            )

    async def handle_nav_back_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.checkin is None or draft.checkout is None:
            return
        session.state = ConversationState.AWAIT_QUOTES_CATEGORY
        category_names = draft.category_names or []
        if query.message is not None:
            await query.edit_message_text(
                render_period_quotes_category_prompt(period_start=draft.checkin, period_end=draft.checkout),
                reply_markup=build_period_quotes_categories_inline_keyboard(category_names=category_names),
            )

    async def handle_back(self, telegram_user_id: int, message, guest_id: str) -> bool:
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state == ConversationState.AWAIT_QUOTES_CATEGORY:
            draft = session.period_quotes
            if draft is not None and draft.month_cursor is not None:
                session.state = ConversationState.AWAIT_QUOTES_CALENDAR
                await message.reply_text(
                    render_period_quotes_calendar_prompt(),
                    reply_markup=build_period_quotes_calendar_inline_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                    ),
                )
                return True
        if session.state == ConversationState.AWAIT_QUOTES_CALENDAR:
            session.state = ConversationState.AWAIT_QUOTES_GROUP
            await message.reply_text(
                render_period_quotes_groups_prompt(),
                reply_markup=build_period_quotes_groups_inline_keyboard(),
            )
            return True
        if session.state == ConversationState.AWAIT_QUOTES_GROUP:
            await self._deps.sessions.reset(telegram_user_id)
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            return True
        return False

    async def _finish_period_quotes_by_calendar(
        self,
        *,
        telegram_user_id: int,
        query,
        group_id: str,
        period_start: date,
        period_end: date,
    ) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            run_id, quotes = self._deps.adapter.get_period_quotes(
                guest_id=guest_id,
                period_start=period_start,
                period_end=period_end,
                group_ids={group_id},
            )
            last_room_dates_by_category: dict[str, list[date]] = {}
            for category_name in {item.category_name for item in quotes}:
                tariffs = {item.tariff for item in quotes if item.category_name == category_name}
                last_room_dates_by_category[category_name] = self._deps.adapter.get_last_room_dates(
                    guest_id=guest_id,
                    category_name=category_name,
                    period_start=period_start,
                    period_end=period_end,
                    tariffs=tariffs,
                )
        except Exception:
            logger.exception("period_quotes_failed user_id=%s guest_id=%s", telegram_user_id, guest_id)
            if query.message is not None:
                await query.message.reply_text(msg("period_quotes_failed"), reply_markup=build_period_quotes_scenario_keyboard())
            await self._deps.sessions.reset(telegram_user_id)
            return

        session = await self._deps.sessions.get(telegram_user_id)
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
        draft.category_names = sorted({item.category_name for item in quotes})
        session.state = ConversationState.AWAIT_QUOTES_CATEGORY

        if query.message is None:
            return

        if not draft.category_names:
            await query.edit_message_text(
                render_period_quotes_empty(period_start=period_start, period_end=period_end),
                reply_markup=build_period_quotes_empty_inline_keyboard(),
            )
            return

        await query.edit_message_text(
            text=render_period_quotes_category_prompt(period_start=period_start, period_end=period_end),
            reply_markup=build_period_quotes_categories_inline_keyboard(category_names=draft.category_names),
        )

    async def _show_category_result(self, *, guest_id: str, telegram_user_id: int, query, category_idx: int) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.checkin is None or draft.checkout is None:
            await query.answer()
            return

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            await query.answer()
            return

        category_name = category_names[category_idx]
        quotes = [item for item in (draft.quotes or []) if item.category_name == category_name]
        if not quotes:
            await query.answer()
            return

        last_room_dates = (draft.last_room_dates_by_category or {}).get(category_name, [])
        has_offer_text = any((item.offer_id or item.offer_title) for item in quotes)

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_period_quote_card(
                    category_name=category_name,
                    period_start=draft.checkin,
                    period_end=draft.checkout,
                    quotes=quotes,
                    last_room_dates=last_room_dates,
                ),
                reply_markup=build_period_quotes_result_inline_keyboard(
                    category_idx=category_idx,
                    has_offer_text=has_offer_text,
                ),
            )
