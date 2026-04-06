from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.callbacks.data_parser import (
    ADMIN_OPEN_REPORTS,
    ADMIN_OPEN_STATISTICS,
    ADMIN_OPEN_SYSTEM,
    ADMIN_REPORT_PARSER_OFFERS,
    ADMIN_REPORT_PARSER_RATES,
    ADMIN_REPORT_RECALCULATION,
    ADMIN_REPORT_TRAVELLINE_PUBLISH,
    ADMIN_REPORT_USER_ERRORS,
    ADMIN_STAT_BLOCKED,
    ADMIN_STAT_NEW_USERS,
    ADMIN_STAT_PRICE_TABLE,
    ADMIN_STAT_TOTAL_USERS,
    ADMIN_SYSTEM_OFFERS,
    ADMIN_SYSTEM_RATES,
    ADMIN_SYSTEM_RECALC,
)


ADMIN_MENU_COMMAND = "/admin_menu"
ADMIN_MENU_TITLE_BUTTON = "🥷🏻 Меню администратора"
ADMIN_GUEST_MENU_BUTTON = "🤵🏻‍♂️ Меню гостя"
ADMIN_SYSTEM_BUTTON = "💻 Система"
ADMIN_REPORTS_BUTTON = "📑 Отчеты"
ADMIN_STATISTICS_BUTTON = "📊 Статистика"
ADMIN_BACK_BUTTON = "🥷🏻 Назад в админ-меню"
ADMIN_RUN_RATES_BUTTON = "▶️ Запустить парсер цен"
ADMIN_RUN_OFFERS_BUTTON = "▶️ Запустить парсер офферов"
ADMIN_RUN_RECALC_BUTTON = "▶️ Запустить пересчет цен"
ADMIN_REPORT_RATES_BUTTON = "Отчеты парсера цен за последнюю неделю"
ADMIN_REPORT_OFFERS_BUTTON = "Отчеты парсера офферов за последнюю неделю"
ADMIN_REPORT_RECALC_BUTTON = "Отчеты пересчета цен за последнюю неделю"
ADMIN_REPORT_ERRORS_BUTTON = "Логи ошибок пользователей за последнюю неделю"
ADMIN_REPORT_TRAVELLINE_PUBLISH_BUTTON = "Travelline publish: последний run"
ADMIN_STATS_TOTAL_USERS_BUTTON = "👥 Всего пользователей"
ADMIN_STATS_PRICE_TABLE_BUTTON = "Таблица цен ожидания в соотношении с категориями"
ADMIN_STATS_NEW_USERS_BUTTON = "Сколько пользователей пришло за последнюю неделю"
ADMIN_STATS_BLOCKED_BUTTON = "Сколько заблокировало бота за последнюю неделю"


def build_admin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_GUEST_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_system_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_BACK_BUTTON)],
            [KeyboardButton(text=ADMIN_GUEST_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_reports_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_BACK_BUTTON)],
            [KeyboardButton(text=ADMIN_GUEST_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_statistics_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_BACK_BUTTON)],
            [KeyboardButton(text=ADMIN_GUEST_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=ADMIN_SYSTEM_BUTTON, callback_data=ADMIN_OPEN_SYSTEM)],
            [InlineKeyboardButton(text=ADMIN_REPORTS_BUTTON, callback_data=ADMIN_OPEN_REPORTS)],
            [InlineKeyboardButton(text=ADMIN_STATISTICS_BUTTON, callback_data=ADMIN_OPEN_STATISTICS)],
        ]
    )


def build_admin_system_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=ADMIN_RUN_RATES_BUTTON, callback_data=ADMIN_SYSTEM_RATES)],
            [InlineKeyboardButton(text=ADMIN_RUN_OFFERS_BUTTON, callback_data=ADMIN_SYSTEM_OFFERS)],
            [InlineKeyboardButton(text=ADMIN_RUN_RECALC_BUTTON, callback_data=ADMIN_SYSTEM_RECALC)],
        ]
    )


def build_admin_reports_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=ADMIN_REPORT_RATES_BUTTON, callback_data=ADMIN_REPORT_PARSER_RATES)],
            [InlineKeyboardButton(text=ADMIN_REPORT_OFFERS_BUTTON, callback_data=ADMIN_REPORT_PARSER_OFFERS)],
            [InlineKeyboardButton(text=ADMIN_REPORT_RECALC_BUTTON, callback_data=ADMIN_REPORT_RECALCULATION)],
            [InlineKeyboardButton(text=ADMIN_REPORT_ERRORS_BUTTON, callback_data=ADMIN_REPORT_USER_ERRORS)],
            [InlineKeyboardButton(text=ADMIN_REPORT_TRAVELLINE_PUBLISH_BUTTON, callback_data=ADMIN_REPORT_TRAVELLINE_PUBLISH)],
        ]
    )


def build_admin_statistics_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=ADMIN_STATS_TOTAL_USERS_BUTTON, callback_data=ADMIN_STAT_TOTAL_USERS)],
            [InlineKeyboardButton(text=ADMIN_STATS_PRICE_TABLE_BUTTON, callback_data=ADMIN_STAT_PRICE_TABLE)],
            [InlineKeyboardButton(text=ADMIN_STATS_NEW_USERS_BUTTON, callback_data=ADMIN_STAT_NEW_USERS)],
            [InlineKeyboardButton(text=ADMIN_STATS_BLOCKED_BUTTON, callback_data=ADMIN_STAT_BLOCKED)],
        ]
    )
