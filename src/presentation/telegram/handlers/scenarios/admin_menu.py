from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.handlers.shared.navigation import send_main_menu_for_guest
from src.presentation.telegram.keyboards.admin_menu import (
    ADMIN_BACK_BUTTON,
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
    build_admin_main_keyboard,
    build_admin_reports_keyboard,
    build_admin_statistics_keyboard,
    build_admin_system_keyboard,
)
from src.presentation.telegram.keyboards.main_menu import build_main_menu_keyboard
from src.presentation.telegram.presenters.admin_menu_presenter import (
    render_admin_access_denied,
    render_admin_main,
    render_admin_report,
    render_admin_reports_menu,
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
        await message.reply_text(render_admin_main(), reply_markup=build_admin_main_keyboard())

    async def handle_flow_text(self, telegram_user_id: int, text: str, message) -> bool:
        if not await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.ADMIN_MENU):
            return False
        if not self.is_admin(telegram_user_id):
            await self._deps.sessions.reset(telegram_user_id)
            await message.reply_text(render_admin_access_denied())
            return True

        session = await self._deps.sessions.get(telegram_user_id)
        if text == ADMIN_SYSTEM_BUTTON:
            session.state = ConversationState.ADMIN_SYSTEM
            await message.reply_text(render_admin_system_menu(), reply_markup=build_admin_system_keyboard())
            return True
        if text == ADMIN_REPORTS_BUTTON:
            session.state = ConversationState.ADMIN_REPORTS
            await message.reply_text(render_admin_reports_menu(), reply_markup=build_admin_reports_keyboard())
            return True
        if text == ADMIN_STATISTICS_BUTTON:
            session.state = ConversationState.ADMIN_STATISTICS
            await message.reply_text(render_admin_statistics_menu(), reply_markup=build_admin_statistics_keyboard())
            return True
        if text == ADMIN_BACK_BUTTON:
            session.state = ConversationState.ADMIN_MENU
            await message.reply_text(render_admin_main(), reply_markup=build_admin_main_keyboard())
            return True

        if session.state == ConversationState.ADMIN_SYSTEM:
            return await self._handle_system_action(telegram_user_id=telegram_user_id, text=text, message=message)
        if session.state == ConversationState.ADMIN_REPORTS:
            return await self._handle_report_action(text=text, message=message)
        if session.state == ConversationState.ADMIN_STATISTICS:
            return await self._handle_statistics_action(text=text, message=message)

        await message.reply_text(render_admin_main(), reply_markup=build_admin_main_keyboard())
        return True

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

    async def handle_back(self, telegram_user_id: int, message) -> bool:
        if not await self._deps.flow_guard.is_active(telegram_user_id, ActiveFlow.ADMIN_MENU):
            return False
        session = await self._deps.sessions.get(telegram_user_id)
        if session.state in {ConversationState.ADMIN_SYSTEM, ConversationState.ADMIN_REPORTS, ConversationState.ADMIN_STATISTICS}:
            session.state = ConversationState.ADMIN_MENU
            await message.reply_text(render_admin_main(), reply_markup=build_admin_main_keyboard())
            return True
        if session.state == ConversationState.ADMIN_MENU:
            await self._deps.sessions.reset(telegram_user_id)
            guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
            if guest_id:
                await send_main_menu_for_guest(deps=self._deps, message=message, guest_id=guest_id)
            else:
                await message.reply_text("Меню администратора закрыто.", reply_markup=build_main_menu_keyboard())
            return True
        return False

