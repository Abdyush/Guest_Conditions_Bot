from __future__ import annotations

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.keyboards.notification_offers import (
    build_notification_categories_inline_keyboard,
    build_notification_groups_inline_keyboard,
    build_notification_offer_text_inline_keyboard,
    build_notification_period_details_inline_keyboard,
    build_notification_periods_inline_keyboard,
    build_notification_scenario_keyboard,
)
from src.presentation.telegram.keyboards.main_menu import build_phone_request_keyboard
from src.presentation.telegram.presenters.available_presenter import (
    build_available_breakfast_periods,
    build_available_groups,
    build_available_periods,
    format_breakfast_period_button_label,
    render_available_period_details,
    render_available_periods_prompt,
)
from src.presentation.telegram.presenters.notification_offers_presenter import (
    render_notification_categories_prompt,
    render_notification_flow_hint,
    render_notification_groups_prompt,
    render_notification_offer_text,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.ui_texts import msg


class NotificationOffersScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.NOTIFICATION_OFFERS)

    async def handle_flow_text(self, telegram_user_id: int, message) -> bool:
        if not await self.is_active(telegram_user_id):
            return False
        await message.reply_text(
            render_notification_flow_hint(),
            reply_markup=build_notification_scenario_keyboard(),
        )
        return True

    async def handle_group_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parsed = _parse_group_callback(data)
        if parsed is None:
            await query.answer()
            return
        run_id, group_idx = parsed

        groups = self._notification_groups_for_guest(guest_id=guest_id, run_id=run_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return

        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_NOTIFICATION_CATEGORY
        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.NOTIFICATION_OFFERS)

        selected_group = groups[group_idx]
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_notification_categories_prompt(group_label=selected_group.label),
                reply_markup=build_notification_categories_inline_keyboard(
                    run_id=run_id,
                    group_idx=group_idx,
                    category_names=selected_group.categories,
                ),
            )

    async def handle_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parsed = _parse_category_callback(data)
        if parsed is None:
            await query.answer()
            return
        run_id, group_idx, category_idx = parsed

        groups = self._notification_groups_for_guest(guest_id=guest_id, run_id=run_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return
        categories = groups[group_idx].categories
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.notifications.get_notification_category_matches(
            guest_id=guest_id,
            run_id=run_id,
            category_name=category_name,
        )
        periods = build_available_breakfast_periods(rows=rows)
        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_NOTIFICATION_PERIOD
        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.NOTIFICATION_OFFERS)

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_periods_prompt(category_name=category_name, periods=periods),
                reply_markup=build_notification_periods_inline_keyboard(
                    run_id=run_id,
                    group_idx=group_idx,
                    category_idx=category_idx,
                    periods=[
                        format_breakfast_period_button_label(start=period.start, end=period.end, price_minor=period.button_price_minor)
                        for period in periods
                    ],
                ),
            )

    async def handle_period_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parsed = _parse_period_callback(data)
        if parsed is None:
            await query.answer()
            return
        run_id, group_idx, category_idx, period_idx = parsed

        groups = self._notification_groups_for_guest(guest_id=guest_id, run_id=run_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return
        categories = groups[group_idx].categories
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.notifications.get_notification_category_matches(
            guest_id=guest_id,
            run_id=run_id,
            category_name=category_name,
        )
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        period = periods[period_idx]
        last_room_dates = self._deps.notifications.get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period.start,
            period_end=period.end,
            tariffs={row.tariff for row in period.rows},
        )
        has_offer = any((row.offer_id or row.offer_title) for row in period.rows)

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_period_details(category_name=category_name, period=period, last_room_dates=last_room_dates),
                reply_markup=build_notification_period_details_inline_keyboard(
                    run_id=run_id,
                    group_idx=group_idx,
                    category_idx=category_idx,
                    period_idx=period_idx,
                    has_offer_text=has_offer,
                ),
            )

    async def handle_offer_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        parsed = _parse_period_callback(data.replace("ntfoff:", "ntfprd:", 1))
        if parsed is None:
            await query.answer()
            return
        run_id, group_idx, category_idx, period_idx = parsed

        groups = self._notification_groups_for_guest(guest_id=guest_id, run_id=run_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return
        categories = groups[group_idx].categories
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return
        category_name = categories[category_idx]

        _, rows = self._deps.notifications.get_notification_category_matches(
            guest_id=guest_id,
            run_id=run_id,
            category_name=category_name,
        )
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return
        period = periods[period_idx]

        row_with_offer = next((row for row in period.rows if row.offer_id or row.offer_title), None)
        if row_with_offer is None:
            await query.answer("Текст специального предложения не найден.", show_alert=False)
            return

        offer_text = self._deps.notifications.get_offer_text(offer_id=row_with_offer.offer_id, offer_title=row_with_offer.offer_title)
        if not offer_text:
            offer_text = "Текст специального предложения недоступен."

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_notification_offer_text(offer_title=row_with_offer.offer_title, offer_text=offer_text),
                reply_markup=build_notification_offer_text_inline_keyboard(
                    run_id=run_id,
                    group_idx=group_idx,
                    category_idx=category_idx,
                    period_idx=period_idx,
                ),
            )

    async def handle_nav_back_groups(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        run_id = _parse_back_groups_callback(data)
        if run_id is None:
            await query.answer()
            return

        groups = self._notification_groups_for_guest(guest_id=guest_id, run_id=run_id)
        session = await self._deps.sessions.get(telegram_user_id)
        session.state = ConversationState.AWAIT_NOTIFICATION_GROUP
        await self._deps.flow_guard.enter(telegram_user_id, ActiveFlow.NOTIFICATION_OFFERS)

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_notification_groups_prompt(),
                reply_markup=build_notification_groups_inline_keyboard(
                    run_id=run_id,
                    group_names=[group.label for group in groups],
                ),
            )

    def _notification_groups_for_guest(self, *, guest_id: str, run_id: str):
        category_groups = self._deps.notifications.get_notification_categories_with_groups(guest_id=guest_id, run_id=run_id)
        return build_available_groups(category_groups=category_groups)


def _parse_group_callback(data: str) -> tuple[str, int] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "ntfgrp":
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


def _parse_category_callback(data: str) -> tuple[str, int, int] | None:
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "ntfcat":
        return None
    try:
        return parts[1], int(parts[2]), int(parts[3])
    except ValueError:
        return None


def _parse_period_callback(data: str) -> tuple[str, int, int, int] | None:
    parts = data.split(":")
    if len(parts) != 5 or parts[0] != "ntfprd":
        return None
    try:
        return parts[1], int(parts[2]), int(parts[3]), int(parts[4])
    except ValueError:
        return None


def _parse_back_groups_callback(data: str) -> str | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "nav" or parts[1] != "back_notification_groups":
        return None
    return parts[2]


