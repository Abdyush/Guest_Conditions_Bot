from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.presentation.telegram.callbacks.data_parser import (
    ADMIN_OPEN_MAIN,
    ADMIN_OPEN_REPORTS,
    ADMIN_OPEN_STATISTICS,
    ADMIN_OPEN_SYSTEM,
    ADMIN_REPORT_PARSER_OFFERS,
    ADMIN_REPORT_PARSER_RATES,
    ADMIN_REPORT_RECALCULATION,
    ADMIN_REPORT_USER_ERRORS,
    ADMIN_STAT_BLOCKED,
    ADMIN_STAT_NEW_USERS,
    ADMIN_STAT_PRICE_TABLE,
    ADMIN_STAT_TOTAL_USERS,
    ADMIN_SYSTEM_OFFERS,
    ADMIN_SYSTEM_RATES,
    ADMIN_SYSTEM_RECALC,
)
from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.admin_menu import (
    ADMIN_BACK_BUTTON,
    ADMIN_GUEST_MENU_BUTTON,
    ADMIN_REPORT_ERRORS_BUTTON,
    ADMIN_REPORT_OFFERS_BUTTON,
    ADMIN_REPORT_RATES_BUTTON,
    ADMIN_REPORT_RECALC_BUTTON,
    ADMIN_REPORTS_BUTTON,
    ADMIN_RUN_OFFERS_BUTTON,
    ADMIN_RUN_RATES_BUTTON,
    ADMIN_RUN_RECALC_BUTTON,
    ADMIN_STATISTICS_BUTTON,
    ADMIN_STATS_BLOCKED_BUTTON,
    ADMIN_STATS_NEW_USERS_BUTTON,
    ADMIN_STATS_PRICE_TABLE_BUTTON,
    ADMIN_STATS_TOTAL_USERS_BUTTON,
    ADMIN_SYSTEM_BUTTON,
    build_admin_main_inline_keyboard,
    build_admin_main_keyboard,
    build_admin_reports_inline_keyboard,
    build_admin_reports_keyboard,
    build_admin_statistics_inline_keyboard,
    build_admin_statistics_keyboard,
    build_admin_system_inline_keyboard,
    build_admin_system_keyboard,
)
from src.presentation.telegram.keyboards.main_menu import build_main_menu_keyboard
from src.presentation.telegram.presenters.admin_menu_presenter import (
    render_admin_access_denied,
    render_admin_main,
    render_admin_main_reply_hint,
    render_admin_report,
    render_admin_reports_menu,
    render_admin_submenu_reply_hint,
    render_admin_statistics_menu,
    render_admin_system_menu,
    render_blocked_users_last_week,
    render_new_users_last_week,
    render_price_expectations_table,
    render_system_attempt_result,
    render_total_users,
)
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState


class AdminMenuScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    def is_admin(self, telegram_user_id: int) -> bool:
        return self._deps.admin_telegram_id is not None and telegram_user_id == self._deps.admin_telegram_id

    async def open_admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        if not self.is_admin(user.id):
            await message.reply_text(render_admin_access_denied())
            return
        session = await self._deps.sessions.get(user.id)
        session.state = ConversationState.ADMIN_MENU
        await self._deps.flow_guard.enter(user.id, ActiveFlow.ADMIN_MENU)
        await self._show_admin_main(message)

    async def handle_flow_text(self, telegram_user_id: int, text: str, message) -> bool:
        if not await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.ADMIN_MENU):
            return False
        if not self.is_admin(telegram_user_id):
            await self._deps.sessions.reset(telegram_user_id)
            await message.reply_text(render_admin_access_denied())
            return True

        session = await self._deps.sessions.get(telegram_user_id)
        if text == ADMIN_GUEST_MENU_BUTTON:
            await self._exit_to_guest_menu(telegram_user_id=telegram_user_id, message=message)
            return True
        if text == ADMIN_SYSTEM_BUTTON:
            session.state = ConversationState.ADMIN_SYSTEM
            await self._show_admin_system(message)
            return True
        if text == ADMIN_REPORTS_BUTTON:
            session.state = ConversationState.ADMIN_REPORTS
            await self._show_admin_reports(message)
            return True
        if text == ADMIN_STATISTICS_BUTTON:
            session.state = ConversationState.ADMIN_STATISTICS
            await self._show_admin_statistics(message)
            return True
        if text == ADMIN_BACK_BUTTON:
            session.state = ConversationState.ADMIN_MENU
            await self._show_admin_main(message)
            return True

        if session.state == ConversationState.ADMIN_SYSTEM:
            return await self._handle_system_action(telegram_user_id=telegram_user_id, text=text, message=message)
        if session.state == ConversationState.ADMIN_REPORTS:
            return await self._handle_report_action(text=text, message=message)
        if session.state == ConversationState.ADMIN_STATISTICS:
            return await self._handle_statistics_action(text=text, message=message)

        await self._show_admin_main(message)
        return True

    async def handle_admin_callback(self, telegram_user_id: int, query, data: str) -> None:
        if not self.is_admin(telegram_user_id):
            await self._deps.sessions.reset(telegram_user_id)
            await query.answer()
            if query.message is not None:
                await query.message.reply_text(render_admin_access_denied())
            return
        if not await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.ADMIN_MENU):
            await query.answer()
            return

        session = await self._deps.sessions.get(telegram_user_id)
        if data == ADMIN_OPEN_MAIN:
            session.state = ConversationState.ADMIN_MENU
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(render_admin_main(), reply_markup=build_admin_main_inline_keyboard())
                await self._show_reply_shell(
                    query.message,
                    text=render_admin_main_reply_hint(),
                    reply_markup=build_admin_main_keyboard(),
                )
            return
        if data == ADMIN_OPEN_SYSTEM:
            session.state = ConversationState.ADMIN_SYSTEM
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(render_admin_system_menu(), reply_markup=build_admin_system_inline_keyboard())
                await self._show_reply_shell(
                    query.message,
                    text=render_admin_submenu_reply_hint(),
                    reply_markup=build_admin_system_keyboard(),
                )
            return
        if data == ADMIN_OPEN_REPORTS:
            session.state = ConversationState.ADMIN_REPORTS
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(render_admin_reports_menu(), reply_markup=build_admin_reports_inline_keyboard())
                await self._show_reply_shell(
                    query.message,
                    text=render_admin_submenu_reply_hint(),
                    reply_markup=build_admin_reports_keyboard(),
                )
            return
        if data == ADMIN_OPEN_STATISTICS:
            session.state = ConversationState.ADMIN_STATISTICS
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(render_admin_statistics_menu(), reply_markup=build_admin_statistics_inline_keyboard())
                await self._show_reply_shell(
                    query.message,
                    text=render_admin_submenu_reply_hint(),
                    reply_markup=build_admin_statistics_keyboard(),
                )
            return

        if session.state == ConversationState.ADMIN_SYSTEM:
            await self._handle_system_callback(telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if session.state == ConversationState.ADMIN_REPORTS:
            await self._handle_report_callback(query=query, data=data)
            return
        if session.state == ConversationState.ADMIN_STATISTICS:
            await self._handle_statistics_callback(query=query, data=data)
            return

        await query.answer()

    async def _handle_system_action(self, *, telegram_user_id: int, text: str, message) -> bool:
        if text == ADMIN_RUN_RATES_BUTTON:
            attempt = await self._deps.pipeline.run_categories_parser(trigger=f"admin_menu:{telegram_user_id}:rates")
            await message.reply_text(
                render_system_attempt_result(
                    title="Запуск парсера цен",
                    attempt_started=attempt.started,
                    attempt_message=attempt.message,
                ),
                reply_markup=build_admin_system_keyboard(),
            )
            return True
        if text == ADMIN_RUN_OFFERS_BUTTON:
            attempt = await self._deps.pipeline.run_offers_parser(trigger=f"admin_menu:{telegram_user_id}:offers")
            await message.reply_text(
                render_system_attempt_result(
                    title="Запуск парсера офферов",
                    attempt_started=attempt.started,
                    attempt_message=attempt.message,
                ),
                reply_markup=build_admin_system_keyboard(),
            )
            return True
        if text == ADMIN_RUN_RECALC_BUTTON:
            attempt = await self._deps.pipeline.run_recalculation(trigger=f"admin_menu:{telegram_user_id}:recalculation")
            await message.reply_text(
                render_system_attempt_result(
                    title="Запуск пересчета цен",
                    attempt_started=attempt.started,
                    attempt_message=attempt.message,
                ),
                reply_markup=build_admin_system_keyboard(),
            )
            return True
        return False

    async def _handle_system_callback(self, *, telegram_user_id: int, query, data: str) -> None:
        if data == ADMIN_SYSTEM_RATES:
            await query.answer()
            attempt = await self._deps.pipeline.run_categories_parser(trigger=f"admin_menu:{telegram_user_id}:rates")
            if query.message is not None:
                await query.edit_message_text(
                    render_system_attempt_result(
                        title="Запуск парсера цен",
                        attempt_started=attempt.started,
                        attempt_message=attempt.message,
                    ),
                    reply_markup=build_admin_system_inline_keyboard(),
                )
            return
        if data == ADMIN_SYSTEM_OFFERS:
            await query.answer()
            attempt = await self._deps.pipeline.run_offers_parser(trigger=f"admin_menu:{telegram_user_id}:offers")
            if query.message is not None:
                await query.edit_message_text(
                    render_system_attempt_result(
                        title="Запуск парсера офферов",
                        attempt_started=attempt.started,
                        attempt_message=attempt.message,
                    ),
                    reply_markup=build_admin_system_inline_keyboard(),
                )
            return
        if data == ADMIN_SYSTEM_RECALC:
            await query.answer()
            attempt = await self._deps.pipeline.run_recalculation(trigger=f"admin_menu:{telegram_user_id}:recalculation")
            if query.message is not None:
                await query.edit_message_text(
                    render_system_attempt_result(
                        title="Запуск пересчета цен",
                        attempt_started=attempt.started,
                        attempt_message=attempt.message,
                    ),
                    reply_markup=build_admin_system_inline_keyboard(),
                )
            return
        await query.answer()

    async def _handle_report_action(self, *, text: str, message) -> bool:
        reports = self._deps.admin.get_admin_reports()
        report_key_by_button = {
            ADMIN_REPORT_RATES_BUTTON: "parser_rates",
            ADMIN_REPORT_OFFERS_BUTTON: "parser_offers",
            ADMIN_REPORT_RECALC_BUTTON: "recalculation",
            ADMIN_REPORT_ERRORS_BUTTON: "user_errors",
        }
        key = report_key_by_button.get(text)
        if key is None:
            return False
        await message.reply_text(render_admin_report(reports[key]), reply_markup=build_admin_reports_keyboard())
        return True

    async def _handle_report_callback(self, *, query, data: str) -> None:
        reports = self._deps.admin.get_admin_reports()
        report_key_by_callback = {
            ADMIN_REPORT_PARSER_RATES: "parser_rates",
            ADMIN_REPORT_PARSER_OFFERS: "parser_offers",
            ADMIN_REPORT_RECALCULATION: "recalculation",
            ADMIN_REPORT_USER_ERRORS: "user_errors",
        }
        key = report_key_by_callback.get(data)
        if key is None:
            await query.answer()
            return
        await query.answer()
        if query.message is not None:
            await query.edit_message_text(render_admin_report(reports[key]), reply_markup=build_admin_reports_inline_keyboard())

    async def _handle_statistics_action(self, *, text: str, message) -> bool:
        stats = self._deps.admin.get_admin_statistics()
        if text == ADMIN_STATS_TOTAL_USERS_BUTTON:
            await message.reply_text(render_total_users(stats.total_users), reply_markup=build_admin_statistics_keyboard())
            return True
        if text == ADMIN_STATS_PRICE_TABLE_BUTTON:
            await message.reply_text(render_price_expectations_table(stats.desired_price_by_group), reply_markup=build_admin_statistics_keyboard())
            return True
        if text == ADMIN_STATS_NEW_USERS_BUTTON:
            await message.reply_text(render_new_users_last_week(stats.new_users_last_week), reply_markup=build_admin_statistics_keyboard())
            return True
        if text == ADMIN_STATS_BLOCKED_BUTTON:
            await message.reply_text(render_blocked_users_last_week(stats.blocked_users_last_week), reply_markup=build_admin_statistics_keyboard())
            return True
        return False

    async def _handle_statistics_callback(self, *, query, data: str) -> None:
        stats = self._deps.admin.get_admin_statistics()
        if data == ADMIN_STAT_TOTAL_USERS:
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(render_total_users(stats.total_users), reply_markup=build_admin_statistics_inline_keyboard())
            return
        if data == ADMIN_STAT_PRICE_TABLE:
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(
                    render_price_expectations_table(stats.desired_price_by_group),
                    reply_markup=build_admin_statistics_inline_keyboard(),
                )
            return
        if data == ADMIN_STAT_NEW_USERS:
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(
                    render_new_users_last_week(stats.new_users_last_week),
                    reply_markup=build_admin_statistics_inline_keyboard(),
                )
            return
        if data == ADMIN_STAT_BLOCKED:
            await query.answer()
            if query.message is not None:
                await query.edit_message_text(
                    render_blocked_users_last_week(stats.blocked_users_last_week),
                    reply_markup=build_admin_statistics_inline_keyboard(),
                )
            return
        await query.answer()

    async def handle_back(self, telegram_user_id: int, message) -> bool:
        if not await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.ADMIN_MENU):
            return False
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state in {ConversationState.ADMIN_SYSTEM, ConversationState.ADMIN_REPORTS, ConversationState.ADMIN_STATISTICS}:
            session.state = ConversationState.ADMIN_MENU
            await self._show_admin_main(message)
            return True
        if session.state == ConversationState.ADMIN_MENU:
            await self._exit_to_guest_menu(telegram_user_id=telegram_user_id, message=message)
            return True
        return False

    async def _show_admin_main(self, message) -> None:
        await message.reply_text(render_admin_main(), reply_markup=build_admin_main_inline_keyboard())
        await self._show_reply_shell(
            message,
            text=render_admin_main_reply_hint(),
            reply_markup=build_admin_main_keyboard(),
        )

    async def _show_admin_system(self, message) -> None:
        await message.reply_text(render_admin_system_menu(), reply_markup=build_admin_system_inline_keyboard())
        await self._show_reply_shell(
            message,
            text=render_admin_submenu_reply_hint(),
            reply_markup=build_admin_system_keyboard(),
        )

    async def _show_admin_reports(self, message) -> None:
        await message.reply_text(render_admin_reports_menu(), reply_markup=build_admin_reports_inline_keyboard())
        await self._show_reply_shell(
            message,
            text=render_admin_submenu_reply_hint(),
            reply_markup=build_admin_reports_keyboard(),
        )

    async def _show_admin_statistics(self, message) -> None:
        await message.reply_text(render_admin_statistics_menu(), reply_markup=build_admin_statistics_inline_keyboard())
        await self._show_reply_shell(
            message,
            text=render_admin_submenu_reply_hint(),
            reply_markup=build_admin_statistics_keyboard(),
        )

    async def _show_reply_shell(self, message, *, text: str, reply_markup) -> None:
        await message.reply_text(text, reply_markup=reply_markup)

    async def _exit_to_guest_menu(self, *, telegram_user_id: int, message) -> None:
        await self._deps.sessions.reset(telegram_user_id)
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if guest_id:
            await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            return
        await message.reply_text("Меню администратора закрыто.", reply_markup=build_main_menu_keyboard())
