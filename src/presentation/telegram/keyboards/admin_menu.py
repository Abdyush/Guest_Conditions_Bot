from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON


ADMIN_MENU_COMMAND = "/admin_menu"
ADMIN_MENU_TITLE_BUTTON = "Меню администратора"
ADMIN_SYSTEM_BUTTON = "Система"
ADMIN_REPORTS_BUTTON = "Отчеты"
ADMIN_STATISTICS_BUTTON = "Статистика"
ADMIN_BACK_BUTTON = "Назад в админ-меню"
ADMIN_RUN_RATES_BUTTON = "Запустить парсер цен"
ADMIN_RUN_OFFERS_BUTTON = "Запустить парсер офферов"
ADMIN_RUN_RECALC_BUTTON = "Запустить пересчет цен"
ADMIN_REPORT_RATES_BUTTON = "Отчеты парсера цен за последнюю неделю"
ADMIN_REPORT_OFFERS_BUTTON = "Отчеты парсера офферов за последнюю неделю"
ADMIN_REPORT_RECALC_BUTTON = "Отчеты пересчета цен за последнюю неделю"
ADMIN_REPORT_ERRORS_BUTTON = "Логи ошибок пользователей за последнюю неделю"
ADMIN_STATS_TOTAL_USERS_BUTTON = "Всего пользователей"
ADMIN_STATS_PRICE_TABLE_BUTTON = "Таблица цен ожидания в соотношении с категориями"
ADMIN_STATS_NEW_USERS_BUTTON = "Сколько пользователей пришло за последнюю неделю"
ADMIN_STATS_BLOCKED_BUTTON = "Сколько заблокировало бота за последнюю неделю"


def build_admin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_SYSTEM_BUTTON)],
            [KeyboardButton(text=ADMIN_REPORTS_BUTTON)],
            [KeyboardButton(text=ADMIN_STATISTICS_BUTTON)],
            [KeyboardButton(text=MAIN_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_system_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_RUN_RATES_BUTTON)],
            [KeyboardButton(text=ADMIN_RUN_OFFERS_BUTTON)],
            [KeyboardButton(text=ADMIN_RUN_RECALC_BUTTON)],
            [KeyboardButton(text=ADMIN_BACK_BUTTON)],
            [KeyboardButton(text=MAIN_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_reports_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_REPORT_RATES_BUTTON)],
            [KeyboardButton(text=ADMIN_REPORT_OFFERS_BUTTON)],
            [KeyboardButton(text=ADMIN_REPORT_RECALC_BUTTON)],
            [KeyboardButton(text=ADMIN_REPORT_ERRORS_BUTTON)],
            [KeyboardButton(text=ADMIN_BACK_BUTTON)],
            [KeyboardButton(text=MAIN_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_admin_statistics_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_STATS_TOTAL_USERS_BUTTON)],
            [KeyboardButton(text=ADMIN_STATS_PRICE_TABLE_BUTTON)],
            [KeyboardButton(text=ADMIN_STATS_NEW_USERS_BUTTON)],
            [KeyboardButton(text=ADMIN_STATS_BLOCKED_BUTTON)],
            [KeyboardButton(text=ADMIN_BACK_BUTTON)],
            [KeyboardButton(text=MAIN_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )
