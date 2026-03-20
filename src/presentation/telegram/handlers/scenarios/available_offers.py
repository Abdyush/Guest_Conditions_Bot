from __future__ import annotations

import logging
from datetime import date

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.keyboards.available_offers import (
    AVREQ_CONTACT_UNAVAILABLE,
    build_available_categories_inline_keyboard,
    build_available_groups_inline_keyboard,
    build_available_offer_text_inline_keyboard,
    build_available_period_details_inline_keyboard,
    build_available_periods_inline_keyboard,
    build_available_request_calendar_inline_keyboard,
    build_available_request_result_inline_keyboard,
    build_available_request_tariff_inline_keyboard,
    build_available_scenario_keyboard,
)
from src.presentation.telegram.keyboards.main_menu import (
    AVAILABLE_ROOMS_BUTTON,
    build_main_menu_keyboard,
    build_notified_categories_inline_keyboard,
    build_notified_period_details_inline_keyboard,
    build_notified_periods_inline_keyboard,
    build_numeric_edit_keyboard,
    build_phone_request_keyboard,
)
from src.presentation.telegram.presenters.available_presenter import (
    build_available_breakfast_periods,
    build_available_groups,
    build_available_periods,
    format_breakfast_period_button_label,
    format_period_button_label,
    render_available_categories_prompt,
    render_available_category_periods,
    render_available_groups_prompt,
    render_available_offer_text,
    render_available_period_details,
    render_available_periods_prompt,
    render_available_request_calendar_prompt,
    render_available_request_tariff_prompt,
    render_available_interest_message,
    tariff_label,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.session_store import AvailableRequestDraft
from src.presentation.telegram.ui_texts import msg


logger = logging.getLogger(__name__)


class AvailableOffersScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def open_available_categories(self, telegram_user_id: int, message) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        groups = self._available_groups_for_guest(guest_id=guest_id)
        session = await self._deps.sessions.get(telegram_user_id)
        session.available_category_names = None
        session.available_category_rows = None
        session.available_request = None
        if not groups:
            await self._deps.flow_guard.leave(telegram_user_id)
            await message.reply_text(msg("available_none"), reply_markup=build_main_menu_keyboard())
            return

        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.AVAILABLE_ROOMS)
        await message.reply_text(
            "Для выхода из сценария используйте кнопку «Главное меню» ниже.",
            reply_markup=build_available_scenario_keyboard(),
        )
        await message.reply_text(
            render_available_groups_prompt(),
            reply_markup=build_available_groups_inline_keyboard(group_names=[group.label for group in groups]),
        )

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.AVAILABLE_ROOMS)

    async def handle_flow_text(self, telegram_user_id: int, text: str, message) -> bool:
        if not await self.is_active(telegram_user_id):
            return False
        if text == AVAILABLE_ROOMS_BUTTON:
            await self.open_available_categories(telegram_user_id, message)
            return True
        await message.reply_text(
            "Сейчас открыт сценарий «Доступные номера». Используйте кнопки этого сценария или кнопку «Главное меню».",
            reply_markup=build_available_scenario_keyboard(),
        )
        return True

    async def handle_available_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parts = data.split(":")
        if len(parts) >= 3 and parts[1] == "grp":
            await self._show_available_group_categories(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
                group_idx_raw=parts[2],
            )
            return
        if len(parts) >= 4 and parts[1] == "cat":
            await self._show_available_category_periods(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
                group_idx_raw=parts[2],
                category_idx_raw=parts[3],
            )
            return

        await query.answer()

    async def handle_available_period_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parts = data.split(":")
        if len(parts) == 4 and parts[1] == "list":
            await self._show_available_category_periods(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
                group_idx_raw=parts[2],
                category_idx_raw=parts[3],
            )
            return
        if len(parts) == 5 and parts[1] == "detail":
            await self._show_available_period_details(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
                group_idx_raw=parts[2],
                category_idx_raw=parts[3],
                period_idx_raw=parts[4],
            )
            return

        await query.answer()

    async def handle_available_offer_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parts = data.split(":")
        if len(parts) != 4:
            await query.answer()
            return

        group_idx, category_idx, period_idx = _parse_three_indices(parts[1], parts[2], parts[3])
        if group_idx is None or category_idx is None or period_idx is None:
            await query.answer()
            return

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=group_idx,
            category_idx=category_idx,
        )
        if context is None:
            await query.answer()
            return
        category_name, rows = context

        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        period = periods[period_idx]
        row_with_offer = next((x for x in period.rows if x.offer_id or x.offer_title), None)
        if row_with_offer is None:
            await query.answer("Текст специального предложения не найден.", show_alert=False)
            return

        offer_text = self._deps.available_offers.get_offer_text(
            offer_id=row_with_offer.offer_id,
            offer_title=row_with_offer.offer_title,
        )
        if not offer_text:
            offer_text = "Текст специального предложения недоступен."

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_offer_text(offer_title=row_with_offer.offer_title, offer_text=offer_text),
                reply_markup=build_available_offer_text_inline_keyboard(
                    group_idx=group_idx,
                    category_idx=category_idx,
                    period_idx=period_idx,
                ),
            )

    async def handle_available_request_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        if data == AVREQ_CONTACT_UNAVAILABLE:
            await self._send_available_request_to_admin(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
            )
            return
        if data.startswith("avreq:start:"):
            await self._start_available_request(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if data.startswith("avreq:cal:"):
            await self._handle_available_request_calendar(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if data.startswith("avreq:tariff:"):
            await self._handle_available_request_tariff(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if data == "avreq:back:detail":
            await self._show_available_request_source_details(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query)
            return
        if data == "avreq:back:calendar":
            session = await self._deps.sessions.get(telegram_user_id)
            draft = session.available_request
            if draft is not None:
                draft.checkin = None
                draft.checkout = None
            await self._show_available_request_calendar(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query)
            return
        if data.startswith("avreq:back:categories:"):
            await self._show_available_request_categories(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, data=data)
            return

        await query.answer()

    async def handle_notified_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        try:
            category_idx = int(data.split(":", 1)[1])
        except ValueError:
            await query.answer()
            return

        categories = self._deps.available_offers.get_available_categories(guest_id=guest_id)
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.available_offers.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)

        await query.answer()
        if query.message is not None:
            if not periods:
                await query.edit_message_text(
                    f"{category_name}\n\nПериоды проживания:\nНет данных.",
                    reply_markup=build_notified_categories_inline_keyboard(category_names=categories),
                )
                return
            labels = [format_period_button_label(start=p.display_start, end=p.end, price_minor=p.min_new_price_minor) for p in periods]
            await query.edit_message_text(
                render_available_category_periods(category_name=category_name, periods=periods),
                reply_markup=build_notified_periods_inline_keyboard(category_idx=category_idx, periods=labels),
            )

    async def handle_notified_period_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

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

        categories = self._deps.available_offers.get_available_categories(guest_id=guest_id)
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.available_offers.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        period = periods[period_idx]
        last_room_dates = self._deps.available_offers.get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period.start,
            period_end=period.end,
            tariffs={x.tariff for x in period.rows},
        )
        has_offer = any((x.offer_id or x.offer_title) for x in period.rows)

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_period_details(category_name=category_name, period=period, last_room_dates=last_room_dates),
                reply_markup=build_notified_period_details_inline_keyboard(
                    category_idx=category_idx,
                    period_idx=period_idx,
                    has_offer_text=has_offer,
                ),
            )

    async def handle_notified_offer_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

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

        categories = self._deps.available_offers.get_available_categories(guest_id=guest_id)
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return
        category_name = categories[category_idx]

        _, rows = self._deps.available_offers.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return
        period = periods[period_idx]

        row_with_offer = next((x for x in period.rows if x.offer_id or x.offer_title), None)
        if row_with_offer is None:
            await query.answer("Текст специального предложения не найден.", show_alert=False)
            return

        offer_text = self._deps.available_offers.get_offer_text(offer_id=row_with_offer.offer_id, offer_title=row_with_offer.offer_title)
        if not offer_text:
            offer_text = "Текст специального предложения недоступен."

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_offer_text(offer_title=row_with_offer.offer_title, offer_text=offer_text),
                reply_markup=build_notified_period_details_inline_keyboard(
                    category_idx=category_idx,
                    period_idx=period_idx,
                    has_offer_text=True,
                ),
            )

    async def handle_nav_back_available_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._deps.flow_guard.leave(telegram_user_id)
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
        session.available_request = None
        groups = self._available_groups_for_guest(guest_id=guest_id)
        if query.message is not None:
            if not groups:
                await self._deps.flow_guard.leave(telegram_user_id)
                await query.edit_message_text(msg("available_none"))
            else:
                await query.edit_message_text(
                    render_available_groups_prompt(),
                    reply_markup=build_available_groups_inline_keyboard(group_names=[group.label for group in groups]),
                )

    async def handle_nav_back_notified_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return
        categories = self._deps.available_offers.get_available_categories(guest_id=guest_id)
        if query.message is not None:
            if not categories:
                await query.edit_message_text(msg("available_none"), reply_markup=build_numeric_edit_keyboard())
            else:
                await query.edit_message_text(
                    "Дорогой гость, по Вашим условиям подошли следующие категории:",
                    reply_markup=build_notified_categories_inline_keyboard(category_names=categories),
                )

    async def _show_available_group_categories(self, *, guest_id: str, telegram_user_id: int, query, group_idx_raw: str) -> None:
        try:
            group_idx = int(group_idx_raw)
        except ValueError:
            await query.answer()
            return

        groups = self._available_groups_for_guest(guest_id=guest_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return

        selected_group = groups[group_idx]
        session = await self._deps.sessions.get(telegram_user_id)
        session.available_category_names = list(selected_group.categories)
        session.available_category_rows = None
        session.available_request = None

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_categories_prompt(group_label=selected_group.label),
                reply_markup=build_available_categories_inline_keyboard(
                    group_idx=group_idx,
                    category_names=selected_group.categories,
                ),
            )

    async def _show_available_category_periods(
        self,
        *,
        guest_id: str,
        telegram_user_id: int,
        query,
        group_idx_raw: str,
        category_idx_raw: str,
    ) -> None:
        parsed = _parse_two_indices(group_idx_raw, category_idx_raw)
        if parsed is None:
            await query.answer()
            return
        group_idx, category_idx = parsed

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=group_idx,
            category_idx=category_idx,
        )
        if context is None:
            await query.answer()
            return
        category_name, rows = context

        periods = build_available_breakfast_periods(rows=rows)
        session = await self._deps.sessions.get(telegram_user_id)
        session.available_request = None

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_periods_prompt(category_name=category_name, periods=periods),
                reply_markup=build_available_periods_inline_keyboard(
                    group_idx=group_idx,
                    category_idx=category_idx,
                    periods=[
                        format_breakfast_period_button_label(start=p.display_start, end=p.end, price_minor=p.button_price_minor)
                        for p in periods
                    ],
                ),
            )

    async def _show_available_period_details(
        self,
        *,
        guest_id: str,
        telegram_user_id: int,
        query,
        group_idx_raw: str,
        category_idx_raw: str,
        period_idx_raw: str,
        preserve_request: bool = False,
    ) -> None:
        parsed = _parse_three_indices(group_idx_raw, category_idx_raw, period_idx_raw)
        if parsed is None:
            await query.answer()
            return
        group_idx, category_idx, period_idx = parsed

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=group_idx,
            category_idx=category_idx,
        )
        if context is None:
            await query.answer()
            return
        category_name, rows = context

        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        session = await self._deps.sessions.get(telegram_user_id)
        if not preserve_request:
            session.available_request = None
        period = periods[period_idx]
        last_room_dates = self._deps.available_offers.get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period.start,
            period_end=period.end,
            tariffs={r.tariff for r in period.rows},
        )
        has_offer = any((x.offer_id or x.offer_title) for x in period.rows)

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_period_details(category_name=category_name, period=period, last_room_dates=last_room_dates),
                reply_markup=build_available_period_details_inline_keyboard(
                    group_idx=group_idx,
                    category_idx=category_idx,
                    period_idx=period_idx,
                    has_offer_text=has_offer,
                ),
            )

    async def _start_available_request(self, *, guest_id: str, telegram_user_id: int, query, data: str) -> None:
        parts = data.split(":")
        if len(parts) != 5:
            await query.answer()
            return

        parsed = _parse_three_indices(parts[2], parts[3], parts[4])
        if parsed is None:
            await query.answer()
            return
        group_idx, category_idx, period_idx = parsed

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=group_idx,
            category_idx=category_idx,
        )
        if context is None:
            await query.answer()
            return
        _, rows = context

        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        source_period = periods[period_idx]
        session = await self._deps.sessions.get(telegram_user_id)
        session.available_request = AvailableRequestDraft(
            group_idx=group_idx,
            category_idx=category_idx,
            source_period_idx=period_idx,
            month_cursor=source_period.display_start.replace(day=1),
            checkin=None,
            checkout=None,
            tariff=None,
            sent_to_admin=False,
        )
        await self._show_available_request_calendar(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
        )

    async def _handle_available_request_calendar(self, *, guest_id: str, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.available_request
        if draft is None or draft.month_cursor is None:
            await query.answer()
            return

        if data == "avreq:cal:noop":
            await query.answer()
            return
        if data.startswith("avreq:cal:nav:"):
            raw = data.split(":", 3)[3]
            try:
                draft.month_cursor = date.fromisoformat(raw).replace(day=1)
            except ValueError:
                await query.answer()
                return
            await query.answer()
            if query.message is not None:
                await query.edit_message_reply_markup(
                    reply_markup=build_available_request_calendar_inline_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                        group_idx=draft.group_idx or 0,
                    )
                )
            return
        if not data.startswith("avreq:cal:day:"):
            await query.answer()
            return

        try:
            picked = date.fromisoformat(data.split(":", 3)[3])
        except ValueError:
            await query.answer()
            return

        if draft.checkin is None:
            draft.checkin = picked
            draft.checkout = None
            draft.month_cursor = picked.replace(day=1)
            await query.answer()
            if query.message is not None:
                await query.edit_message_reply_markup(
                    reply_markup=build_available_request_calendar_inline_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                        group_idx=draft.group_idx or 0,
                    )
                )
            return

        if draft.checkout is None:
            if picked <= draft.checkin:
                draft.checkin = picked
                draft.checkout = None
                draft.month_cursor = picked.replace(day=1)
                await query.answer()
                if query.message is not None:
                    await query.edit_message_reply_markup(
                        reply_markup=build_available_request_calendar_inline_keyboard(
                            month_cursor=draft.month_cursor,
                            checkin=draft.checkin,
                            checkout=None,
                            group_idx=draft.group_idx or 0,
                        )
                    )
                return

            draft.checkout = picked
            await self._show_available_request_tariff(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
            )
            return

        await query.answer()

    async def _handle_available_request_tariff(self, *, guest_id: str, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.available_request
        if draft is None or draft.checkin is None or draft.checkout is None:
            await query.answer()
            return

        tariff_code = data.split(":", 2)[2].strip().lower()
        if tariff_code not in {"breakfast", "fullpansion"}:
            await query.answer()
            return
        draft.tariff = tariff_code
        draft.sent_to_admin = False

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=draft.group_idx,
            category_idx=draft.category_idx,
        )
        if context is None:
            await query.answer()
            return
        category_name, rows = context

        profile = self._deps.profile.get_guest_profile(guest_id=guest_id)
        if profile is None:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return
        open_price_minor, preliminary_price_minor, loyalty_status, special_offers = self._resolve_available_request_quote_summary(
            guest_id=guest_id,
            category_name=category_name,
            period_start=draft.checkin,
            period_end=draft.checkout,
            tariff=draft.tariff,
            rows=rows,
        )

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_interest_message(
                    category_name=category_name,
                    period_start=draft.checkin,
                    period_end=draft.checkout,
                    tariff_label=tariff_label(draft.tariff),
                    open_price_minor=open_price_minor,
                    preliminary_price_minor=preliminary_price_minor,
                    adults=profile.occupancy.adults,
                    loyalty_status=loyalty_status,
                    special_offers=special_offers,
                    children_4_13=profile.occupancy.children_4_13,
                    infants_0_3=profile.occupancy.infants,
                ),
                reply_markup=build_available_request_result_inline_keyboard(
                    group_idx=draft.group_idx or 0,
                    contact_url=self._responsible_contact_url(),
                ),
            )

    async def _show_available_request_calendar(self, *, guest_id: str, telegram_user_id: int, query) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.available_request
        if draft is None or draft.month_cursor is None:
            await query.answer()
            return

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=draft.group_idx,
            category_idx=draft.category_idx,
        )
        if context is None:
            await query.answer()
            return
        category_name, _ = context

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_request_calendar_prompt(category_name=category_name),
                reply_markup=build_available_request_calendar_inline_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                    group_idx=draft.group_idx or 0,
                ),
            )

    async def _show_available_request_tariff(self, *, guest_id: str, telegram_user_id: int, query) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.available_request
        if draft is None or draft.checkin is None or draft.checkout is None:
            await query.answer()
            return

        context = await self._resolve_available_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            group_idx=draft.group_idx,
            category_idx=draft.category_idx,
        )
        if context is None:
            await query.answer()
            return
        category_name, _ = context

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_request_tariff_prompt(
                    category_name=category_name,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                ),
                reply_markup=build_available_request_tariff_inline_keyboard(group_idx=draft.group_idx or 0),
            )

    async def _show_available_request_source_details(self, *, guest_id: str, telegram_user_id: int, query) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.available_request
        if draft is None or draft.group_idx is None or draft.category_idx is None or draft.source_period_idx is None:
            await query.answer()
            return
        await self._show_available_period_details(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            group_idx_raw=str(draft.group_idx),
            category_idx_raw=str(draft.category_idx),
            period_idx_raw=str(draft.source_period_idx),
            preserve_request=True,
        )

    async def _show_available_request_categories(self, *, guest_id: str, telegram_user_id: int, query, data: str) -> None:
        session = await self._deps.sessions.get(telegram_user_id)
        draft = session.available_request
        group_idx_raw = data.split(":")[-1]
        if draft is not None and draft.group_idx is not None:
            group_idx_raw = str(draft.group_idx)
        session.available_request = None
        await self._show_available_group_categories(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            query=query,
            group_idx_raw=group_idx_raw,
        )

    async def _resolve_available_context(
        self,
        *,
        guest_id: str,
        telegram_user_id: int,
        group_idx: int | None,
        category_idx: int | None,
    ) -> tuple[str, list] | None:
        if group_idx is None or category_idx is None:
            return None

        groups = self._available_groups_for_guest(guest_id=guest_id)
        if group_idx < 0 or group_idx >= len(groups):
            return None

        categories = groups[group_idx].categories
        if category_idx < 0 or category_idx >= len(categories):
            return None

        category_name = categories[category_idx]
        session = await self._deps.sessions.get(telegram_user_id)
        _, rows = self._deps.available_offers.get_category_matches(guest_id=guest_id, category_name=category_name)
        session.available_category_rows = rows
        session.available_category_names = list(categories)
        return category_name, rows

    def _resolve_available_request_quote_summary(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariff: str,
        rows: list,
    ) -> tuple[int | None, int | None, str | None, list[tuple[date, date, str]]]:
        group_ids = {row.group_id for row in rows if getattr(row, "group_id", None)}
        _, quotes = self._deps.period_quotes.get_period_quotes(
            guest_id=guest_id,
            period_start=period_start,
            period_end=period_end,
            group_ids=group_ids or None,
        )
        matching_quotes = [
            quote
            for quote in quotes
            if quote.category_name == category_name and quote.tariff.strip().lower() == tariff
        ]
        if not matching_quotes:
            return None, None, None, []

        open_price_minor = sum(quote.total_old_minor for quote in matching_quotes)
        preliminary_price_minor = sum(quote.total_new_minor for quote in matching_quotes)
        loyalty_status = next((quote.loyalty_status for quote in matching_quotes if quote.loyalty_status), None)

        special_offers: list[tuple[date, date, str]] = []
        seen_offers: set[tuple[date, date, str]] = set()
        for quote in matching_quotes:
            if not quote.offer_title:
                continue
            offer_key = (quote.applied_from, quote.applied_to, quote.offer_title)
            if offer_key in seen_offers:
                continue
            seen_offers.add(offer_key)
            special_offers.append(offer_key)

        return open_price_minor, preliminary_price_minor, loyalty_status, special_offers

    async def _send_available_request_to_admin(self, *, guest_id: str, telegram_user_id: int, query) -> None:
        await query.answer("??????? ?????????????? ?? ????????.", show_alert=True)

    def _responsible_contact_url(self) -> str | None:
        if self._deps.admin_telegram_id is None:
            return None
        return f"tg://user?id={self._deps.admin_telegram_id}"

    def _available_groups_for_guest(self, *, guest_id: str):
        category_groups = self._deps.available_offers.get_available_categories_with_groups(guest_id=guest_id)
        return build_available_groups(category_groups=category_groups)


def _parse_two_indices(first: str, second: str) -> tuple[int, int] | None:
    try:
        return int(first), int(second)
    except ValueError:
        return None


def _parse_three_indices(first: str, second: str, third: str) -> tuple[int, int, int] | None:
    try:
        return int(first), int(second), int(third)
    except ValueError:
        return None

