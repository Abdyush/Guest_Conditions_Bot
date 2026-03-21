from __future__ import annotations

import logging
from datetime import date

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.handlers.subflows.interest_request import (
    InterestRequestStartContext,
    InterestRequestSubflow,
)
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
        self._interest_request = InterestRequestSubflow(
            deps=deps,
            adapter=_PeriodQuotesInterestRequestAdapter(self),
        )

    async def open_group_picker(self, *, telegram_user_id: int, message) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_QUOTES_CALENDAR
        session.period_quotes = PeriodQuotesDraft(
            group_id=None,
            month_cursor=date.today().replace(day=1),
            checkin=None,
            checkout=None,
        )
        session.interest_request = None
        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.PERIOD_QUOTES)
        await message.reply_text(
            "Сценарий «Цены на период» открыт. Для выхода используйте кнопку «Главное меню» ниже.",
            reply_markup=build_period_quotes_scenario_keyboard(),
        )
        await message.reply_text(
            text=render_period_quotes_calendar_prompt(),
            reply_markup=build_period_quotes_calendar_inline_keyboard(
                month_cursor=session.period_quotes.month_cursor,
                checkin=session.period_quotes.checkin,
                checkout=session.period_quotes.checkout,
            ),
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
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        group_id = data.split(":", 1)[1].strip().upper()
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if session.state != ConversationState.AWAIT_QUOTES_GROUP or draft is None or draft.checkin is None or draft.checkout is None:
            await query.answer()
            return

        category_names = self._category_names_for_group(quotes=draft.quotes or [], group_id=group_id)
        if not category_names:
            await query.answer()
            return

        draft.group_id = group_id
        draft.category_names = category_names
        session.interest_request = None
        session.state = ConversationState.AWAIT_QUOTES_CATEGORY
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                text=render_period_quotes_category_prompt(period_start=draft.checkin, period_end=draft.checkout),
                reply_markup=build_period_quotes_categories_inline_keyboard(category_names=category_names),
            )

    async def handle_calendar_callback(self, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if session.state != ConversationState.AWAIT_QUOTES_CALENDAR or draft is None or draft.month_cursor is None:
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
                period_start=draft.checkin,
                period_end=draft.checkout,
            )
            return

        await query.answer()

    async def handle_quotes_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
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
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
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
        if draft is None or draft.group_id is None:
            await query.answer()
            return

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            await query.answer()
            return

        category_name = category_names[category_idx]
        quotes = [
            item
            for item in (draft.quotes or [])
            if item.category_name == category_name and item.group_id == draft.group_id
        ]
        row_with_offer = next((item for item in quotes if item.offer_id or item.offer_title), None)
        if row_with_offer is None:
            await query.answer("Текст специального предложения не найден.", show_alert=False)
            return

        offer_text = self._deps.period_quotes.get_offer_text(
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
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
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

    async def handle_interest_request_callback(self, telegram_user_id: int, query, data: str) -> None:
        await self._interest_request.handle_callback(
            telegram_user_id=telegram_user_id,
            query=query,
            data=data,
        )

    async def handle_nav_back_group(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.month_cursor is None:
            return
        session.interest_request = None
        session.state = ConversationState.AWAIT_QUOTES_CALENDAR
        if draft.checkin is not None:
            draft.month_cursor = draft.checkin.replace(day=1)
        draft.group_id = None
        draft.category_names = None
        draft.run_id = None
        draft.quotes = None
        draft.last_room_dates_by_category = None
        draft.checkin = None
        draft.checkout = None
        if query.message is not None:
            await query.edit_message_text(
                text=render_period_quotes_calendar_prompt(),
                reply_markup=build_period_quotes_calendar_inline_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                ),
            )

    async def handle_nav_back_calendar(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.checkin is None or draft.checkout is None:
            return
        session.interest_request = None
        session.state = ConversationState.AWAIT_QUOTES_GROUP
        draft.group_id = None
        draft.category_names = None
        available_group_ids = self._available_group_ids_from_quotes(draft.quotes or [])
        if query.message is not None:
            await query.edit_message_text(
                render_period_quotes_groups_prompt(),
                reply_markup=build_period_quotes_groups_inline_keyboard(group_ids=available_group_ids),
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
            if draft is not None and draft.checkin is not None and draft.checkout is not None:
                session.interest_request = None
                session.state = ConversationState.AWAIT_QUOTES_GROUP
                draft.group_id = None
                draft.category_names = None
                available_group_ids = self._available_group_ids_from_quotes(draft.quotes or [])
                await message.reply_text(
                    render_period_quotes_groups_prompt(),
                    reply_markup=build_period_quotes_groups_inline_keyboard(group_ids=available_group_ids),
                )
                return True
        if session.state == ConversationState.AWAIT_QUOTES_GROUP:
            draft = session.period_quotes
            if draft is not None and draft.month_cursor is not None:
                session.interest_request = None
                session.state = ConversationState.AWAIT_QUOTES_CALENDAR
                if draft.checkin is not None:
                    draft.month_cursor = draft.checkin.replace(day=1)
                draft.group_id = None
                draft.category_names = None
                draft.run_id = None
                draft.quotes = None
                draft.last_room_dates_by_category = None
                draft.checkin = None
                draft.checkout = None
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
            await self._deps.sessions.reset(telegram_user_id)
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            return True
        return False

    async def _finish_period_quotes_by_calendar(
        self,
        *,
        telegram_user_id: int,
        query,
        period_start: date,
        period_end: date,
    ) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await self._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            run_id, quotes = self._deps.period_quotes.get_period_quotes(
                guest_id=guest_id,
                period_start=period_start,
                period_end=period_end,
                group_ids=None,
            )
            last_room_dates_by_category: dict[str, list[date]] = {}
            for category_name in {item.category_name for item in quotes}:
                tariffs = {item.tariff for item in quotes if item.category_name == category_name}
                last_room_dates_by_category[category_name] = self._deps.period_quotes.get_last_room_dates(
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
        draft.group_id = None
        draft.checkin = period_start
        draft.checkout = period_end
        draft.run_id = run_id
        draft.quotes = quotes
        draft.last_room_dates_by_category = last_room_dates_by_category
        draft.category_names = None
        session.interest_request = None
        session.state = ConversationState.AWAIT_QUOTES_GROUP

        if query.message is None:
            return

        available_group_ids = self._available_group_ids_from_quotes(quotes)
        if not available_group_ids:
            await query.edit_message_text(
                render_period_quotes_empty(period_start=period_start, period_end=period_end),
                reply_markup=build_period_quotes_empty_inline_keyboard(),
            )
            return

        await query.edit_message_text(
            text=render_period_quotes_groups_prompt(),
            reply_markup=build_period_quotes_groups_inline_keyboard(group_ids=available_group_ids),
        )

    async def _show_category_result(self, *, guest_id: str, telegram_user_id: int, query, category_idx: int) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.checkin is None or draft.checkout is None or draft.group_id is None:
            await query.answer()
            return

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            await query.answer()
            return

        category_name = category_names[category_idx]
        quotes = [
            item
            for item in (draft.quotes or [])
            if item.category_name == category_name and item.group_id == draft.group_id
        ]
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
                    interest_callback_data=f"avreq:start:quotes:{category_idx}",
                    has_offer_text=has_offer_text,
                ),
            )

    async def _show_interest_request_source_result(self, *, guest_id: str, telegram_user_id: int, query, category_idx: int) -> None:
        await self._show_category_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            category_idx=category_idx,
        )

    async def _show_interest_request_categories(self, *, telegram_user_id: int, query) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.checkin is None or draft.checkout is None:
            await query.answer()
            return
        session.state = ConversationState.AWAIT_QUOTES_CATEGORY
        if query.message is not None:
            await query.answer()
            await query.edit_message_text(
                render_period_quotes_category_prompt(period_start=draft.checkin, period_end=draft.checkout),
                reply_markup=build_period_quotes_categories_inline_keyboard(category_names=draft.category_names or []),
            )

    async def _resolve_interest_request_start_context(
        self,
        *,
        telegram_user_id: int,
        data: str,
    ) -> InterestRequestStartContext | None:
        parts = data.split(":")
        if len(parts) != 4 or parts[2] != "quotes":
            return None
        try:
            category_idx = int(parts[3])
        except ValueError:
            return None

        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.period_quotes
        if draft is None or draft.group_id is None or draft.checkin is None or draft.checkout is None:
            return None

        category_names = draft.category_names or []
        if category_idx < 0 or category_idx >= len(category_names):
            return None

        return InterestRequestStartContext(
            period_mode="fixed",
            source_kind="quotes",
            category_name=category_names[category_idx],
            month_cursor=draft.checkin.replace(day=1),
            checkin=draft.checkin,
            checkout=draft.checkout,
            quote_group_ids=[draft.group_id],
            source_group_id=draft.group_id,
            source_category_idx=category_idx,
        )

    @staticmethod
    def _available_group_ids_from_quotes(quotes) -> list[str]:
        return sorted({item.group_id for item in quotes if item.group_id})

    @staticmethod
    def _category_names_for_group(*, quotes, group_id: str) -> list[str]:
        return sorted({item.category_name for item in quotes if item.group_id == group_id})


class _PeriodQuotesInterestRequestAdapter:
    calendar_parent_back_text = "\u041d\u0430\u0437\u0430\u0434 \u043a \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f\u043c"
    result_parent_back_text = "\u041d\u0430\u0437\u0430\u0434 \u043a \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f\u043c"

    def __init__(self, scenario: PeriodQuotesScenario):
        self._scenario = scenario

    async def handle_missing_guest(self, *, telegram_user_id: int, query) -> None:
        await self._scenario._deps.flow_guard.leave(telegram_user_id)
        await self._scenario._deps.sessions.set_state(telegram_user_id, ConversationState.AWAIT_PHONE_CONTACT)
        await query.answer()
        if query.message is not None:
            await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())

    async def resolve_start_context(
        self,
        *,
        guest_id: str,
        telegram_user_id: int,
        data: str,
    ) -> InterestRequestStartContext | None:
        return await self._scenario._resolve_interest_request_start_context(
            telegram_user_id=telegram_user_id,
            data=data,
        )

    async def show_source_screen(self, *, guest_id: str, telegram_user_id: int, query, draft) -> None:
        if draft.source_category_idx is None:
            await query.answer()
            return
        await self._scenario._show_interest_request_source_result(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            category_idx=draft.source_category_idx,
        )

    async def show_parent_screen(self, *, guest_id: str, telegram_user_id: int, query, draft) -> None:
        await self._scenario._show_interest_request_categories(
            telegram_user_id=telegram_user_id,
            query=query,
        )

    async def show_period_screen(self, *, guest_id: str, telegram_user_id: int, query, draft) -> None:
        await self._scenario.handle_nav_back_group(telegram_user_id, query)
