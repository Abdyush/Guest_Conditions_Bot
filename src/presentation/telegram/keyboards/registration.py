from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.main_menu import BACK_BUTTON, MAIN_MENU_BUTTON
from src.presentation.telegram.ui_texts import BANK_LABEL_TO_CODE, CATEGORY_LABEL_TO_CODE, LOYALTY_OPTIONS


REGISTRATION_ALL_CATEGORIES_BUTTON = "Все категории"
REGISTRATION_GROUPS_DONE_BUTTON = "Готово"
REGISTRATION_LOYALTY_NO_STATUS_BUTTON = "Без статуса"


def build_registration_navigation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )


def build_registration_numeric_keyboard() -> ReplyKeyboardMarkup:
    return build_registration_navigation_keyboard()


def build_registration_categories_inline_keyboard(*, selected_codes: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        prefix = "✅ " if code in selected_codes else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"regcat:{code}")])

    all_codes = set(CATEGORY_LABEL_TO_CODE.values())
    all_prefix = "✅ " if selected_codes and selected_codes == all_codes else ""
    rows.append([InlineKeyboardButton(text=f"{all_prefix}{REGISTRATION_ALL_CATEGORIES_BUTTON}", callback_data="regcat:all")])
    rows.append([InlineKeyboardButton(text=REGISTRATION_GROUPS_DONE_BUTTON, callback_data="regcat:done")])
    return InlineKeyboardMarkup(rows)


def build_registration_loyalty_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=REGISTRATION_LOYALTY_NO_STATUS_BUTTON), KeyboardButton(text=LOYALTY_OPTIONS[0])],
            [KeyboardButton(text=LOYALTY_OPTIONS[1]), KeyboardButton(text=LOYALTY_OPTIONS[2]), KeyboardButton(text=LOYALTY_OPTIONS[3])],
            [KeyboardButton(text=LOYALTY_OPTIONS[4]), KeyboardButton(text=LOYALTY_OPTIONS[5])],
            [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MAIN_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_registration_bank_keyboard() -> ReplyKeyboardMarkup:
    labels = list(BANK_LABEL_TO_CODE.keys())
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0])],
            [KeyboardButton(text=labels[1]), KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
            [KeyboardButton(text=BACK_BUTTON), KeyboardButton(text=MAIN_MENU_BUTTON)],
        ],
        resize_keyboard=True,
    )
