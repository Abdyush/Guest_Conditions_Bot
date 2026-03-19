from __future__ import annotations

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.keyboards.available_offers import (
    build_available_categories_inline_keyboard,
    build_available_groups_inline_keyboard,
    build_available_offer_text_inline_keyboard,
    build_available_period_details_inline_keyboard,
    build_available_periods_inline_keyboard,
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
    build_available_groups,
    build_available_breakfast_periods,
    build_available_periods,
    format_breakfast_period_button_label,
    format_period_button_label,
    render_available_category_periods,
    render_available_categories_prompt,
    render_available_groups_prompt,
    render_available_offer_text,
    render_available_period_details,
    render_available_periods_prompt,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.ui_texts import msg


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
            await self._show_available_group_categories(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, group_idx_raw=parts[2])
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

        groups = self._available_groups_for_guest(guest_id=guest_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return
        categories = groups[group_idx].categories
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
                reply_markup=build_available_offer_text_inline_keyboard(
                    group_idx=group_idx,
                    category_idx=category_idx,
                    period_idx=period_idx,
                ),
            )

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
            labels = [format_period_button_label(start=p.start, end=p.end, price_minor=p.min_new_price_minor) for p in periods]
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

        groups = self._available_groups_for_guest(guest_id=guest_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return
        categories = groups[group_idx].categories
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.available_offers.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_breakfast_periods(rows=rows)
        session = await self._deps.sessions.get(telegram_user_id)
        session.available_category_names = list(categories)
        session.available_category_rows = rows

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_periods_prompt(category_name=category_name, periods=periods),
                reply_markup=build_available_periods_inline_keyboard(
                    group_idx=group_idx,
                    category_idx=category_idx,
                    periods=[
                        format_breakfast_period_button_label(start=p.start, end=p.end, price_minor=p.button_price_minor)
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
    ) -> None:
        parsed = _parse_three_indices(group_idx_raw, category_idx_raw, period_idx_raw)
        if parsed is None:
            await query.answer()
            return
        group_idx, category_idx, period_idx = parsed

        groups = self._available_groups_for_guest(guest_id=guest_id)
        if group_idx < 0 or group_idx >= len(groups):
            await query.answer()
            return
        categories = groups[group_idx].categories
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        session = await self._deps.sessions.get(telegram_user_id)
        rows = session.available_category_rows or []
        if not rows:
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


