from __future__ import annotations

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.keyboards.main_menu import (
    build_available_categories_inline_keyboard,
    build_available_period_details_inline_keyboard,
    build_available_periods_inline_keyboard,
    build_notified_categories_inline_keyboard,
    build_notified_period_details_inline_keyboard,
    build_notified_periods_inline_keyboard,
    build_numeric_edit_keyboard,
    build_phone_request_keyboard,
)
from src.presentation.telegram.presenters.available_presenter import (
    build_available_periods,
    format_period_button_label,
    render_available_category_periods,
    render_available_period_details,
)
from src.presentation.telegram.ui_texts import msg


class AvailableOffersScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def open_available_categories(self, telegram_user_id: int, message) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return
        categories = self._deps.adapter.get_available_categories(guest_id=guest_id)
        session = await self._deps.sessions.get(telegram_user_id)
        session.available_category_names = categories
        session.available_category_rows = None
        if not categories:
            await message.reply_text(msg("available_none"), reply_markup=build_numeric_edit_keyboard())
            return
        await message.reply_text(msg("available_pick_category"), reply_markup=build_available_categories_inline_keyboard(category_names=categories))

    async def handle_available_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
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
        _, rows = self._deps.adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)
        session.available_category_rows = rows
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_category_periods(category_name=category_name, periods=periods),
                reply_markup=build_available_periods_inline_keyboard(
                    category_idx=idx,
                    periods=[
                        (p.start, p.end, format_period_button_label(start=p.start, end=p.end, price_minor=p.min_new_price_minor))
                        for p in periods
                    ],
                ),
            )

    async def handle_available_period_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return

        session = await self._deps.sessions.get(telegram_user_id)
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
            _, rows = self._deps.adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        period = periods[period_idx]
        last_room_dates = self._deps.adapter.get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period.start,
            period_end=period.end,
            tariffs={r.tariff for r in period.rows},
        )
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_available_period_details(category_name=category_name, period=period, last_room_dates=last_room_dates),
                reply_markup=build_available_period_details_inline_keyboard(category_idx=category_idx),
            )

    async def handle_notified_category_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
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

        categories = self._deps.adapter.get_available_categories(guest_id=guest_id)
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
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
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
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

        categories = self._deps.adapter.get_available_categories(guest_id=guest_id)
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return

        category_name = categories[category_idx]
        _, rows = self._deps.adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return

        period = periods[period_idx]
        last_room_dates = self._deps.adapter.get_last_room_dates(
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
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
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

        categories = self._deps.adapter.get_available_categories(guest_id=guest_id)
        if category_idx < 0 or category_idx >= len(categories):
            await query.answer()
            return
        category_name = categories[category_idx]

        _, rows = self._deps.adapter.get_category_matches(guest_id=guest_id, category_name=category_name)
        periods = build_available_periods(rows=rows)
        if period_idx < 0 or period_idx >= len(periods):
            await query.answer()
            return
        period = periods[period_idx]

        row_with_offer = next((x for x in period.rows if x.offer_id or x.offer_title), None)
        if row_with_offer is None:
            await query.answer("Текст специального предложения не найден.", show_alert=False)
            return

        offer_text = self._deps.adapter.get_offer_text(offer_id=row_with_offer.offer_id, offer_title=row_with_offer.offer_title)
        if not offer_text:
            offer_text = "Текст специального предложения недоступен."

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                offer_text,
                reply_markup=build_notified_period_details_inline_keyboard(
                    category_idx=category_idx,
                    period_idx=period_idx,
                    has_offer_text=True,
                ),
            )

    async def handle_nav_back_available_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        session = await self._deps.sessions.get(telegram_user_id)
        categories = session.available_category_names or []
        if query.message is not None:
            await query.edit_message_text(
                msg("available_pick_category"),
                reply_markup=build_available_categories_inline_keyboard(category_names=categories),
            )

    async def handle_nav_back_notified_categories(self, telegram_user_id: int, query) -> None:
        await query.answer()
        guest_id = self._deps.adapter.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            if query.message is not None:
                await query.message.reply_text(msg("auth_required"), reply_markup=build_phone_request_keyboard())
            return
        categories = self._deps.adapter.get_available_categories(guest_id=guest_id)
        if query.message is not None:
            if not categories:
                await query.edit_message_text(msg("available_none"), reply_markup=build_numeric_edit_keyboard())
            else:
                await query.edit_message_text(
                    "Дорогой гость, по вашим условиям подошли следующие категории:",
                    reply_markup=build_notified_categories_inline_keyboard(category_names=categories),
                )
