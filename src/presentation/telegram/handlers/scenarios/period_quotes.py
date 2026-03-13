from __future__ import annotations

import logging
from datetime import date

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.calendar_picker import build_period_calendar_keyboard, first_day_of_month
from src.presentation.telegram.keyboards.main_menu import (
    build_numeric_edit_keyboard,
    build_phone_request_keyboard,
    build_quotes_categories_inline_keyboard,
    build_quotes_category_details_inline_keyboard,
    build_quotes_group_inline_keyboard,
)
from src.presentation.telegram.presenters.message_presenter import render_period_quotes
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import PeriodQuotesDraft
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)


class PeriodQuotesScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def open_group_picker(self, *, telegram_user_id: int, message) -> None:
        await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_QUOTES_GROUP)
        session = await self._deps.sessions.get(telegram_user_id)
        session.period_quotes = None
        await message.reply_text(msg("ask_quotes_group"), reply_markup=build_quotes_group_inline_keyboard())

    async def handle_quotes_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
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

    async def handle_quotes_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
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

    async def handle_nav_back_group(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_QUOTES_GROUP
        if query.message is not None:
            await query.edit_message_text(msg("ask_quotes_group"), reply_markup=build_quotes_group_inline_keyboard())

    async def handle_nav_back_calendar(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
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

    async def handle_nav_back_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
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

    async def handle_back(self, telegram_user_id: int, message, guest_id: str) -> bool:
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state == ConversationState.AWAIT_QUOTES_CATEGORY:
            draft = session.period_quotes
            if draft is not None and draft.month_cursor is not None:
                session.state = ConversationState.AWAIT_QUOTES_CALENDAR
                await message.reply_text(
                    msg("ask_quotes_calendar"),
                    reply_markup=build_period_calendar_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                    ),
                )
                return True
        if session.state == ConversationState.AWAIT_QUOTES_CALENDAR:
            session.state = ConversationState.AWAIT_QUOTES_GROUP
            await message.reply_text(msg("ask_quotes_group"), reply_markup=build_quotes_group_inline_keyboard())
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
            for category_name in {q.category_name for q in quotes}:
                tariffs = {q.tariff for q in quotes if q.category_name == category_name}
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
                await query.message.reply_text(msg("period_quotes_failed"))
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
        draft.category_names = sorted({q.category_name for q in quotes})
        session.state = ConversationState.AWAIT_QUOTES_CATEGORY

        if query.message is not None:
            if not draft.category_names:
                await query.message.reply_text(
                    f"Нет вариантов на период {period_start.isoformat()} - {period_end.isoformat()}.",
                    reply_markup=build_numeric_edit_keyboard(),
                )
                await self._deps.sessions.reset(telegram_user_id)
                return
            await query.edit_message_text(
                text="Выберите категорию:",
                reply_markup=build_quotes_categories_inline_keyboard(category_names=draft.category_names),
            )
