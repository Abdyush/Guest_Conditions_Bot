from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON
from src.presentation.telegram.ui_texts import BANK_LABEL_TO_CODE, BUTTONS, CATEGORY_LABEL_TO_CODE, LOYALTY_OPTIONS


def build_edit_profile_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )


def build_edit_menu_inline_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=BUTTONS["edit_adults"], callback_data="editfld:adults")],
        [InlineKeyboardButton(text=BUTTONS["edit_children"], callback_data="editfld:children")],
        [InlineKeyboardButton(text=BUTTONS["edit_infants"], callback_data="editfld:infants")],
        [InlineKeyboardButton(text=BUTTONS["edit_groups"], callback_data="editfld:groups")],
        [InlineKeyboardButton(text=BUTTONS["edit_loyalty"], callback_data="editfld:loyalty")],
        [InlineKeyboardButton(text=BUTTONS["edit_bank"], callback_data="editfld:bank")],
        [InlineKeyboardButton(text=BUTTONS["edit_price"], callback_data="editfld:price")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="editfld:back")],
    ]
    return InlineKeyboardMarkup(rows)


def build_edit_numeric_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=BUTTONS["back"], callback_data="editnav:back")]]
    )


def build_edit_loyalty_inline_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for value in LOYALTY_OPTIONS:
        rows.append([InlineKeyboardButton(text=value, callback_data=f"editloy:{value}")])
    rows.append([InlineKeyboardButton(text=BUTTONS["back"], callback_data="editnav:back")])
    return InlineKeyboardMarkup(rows)


def build_edit_bank_inline_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in BANK_LABEL_TO_CODE.items():
        value = code or "none"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"editbank:{value}")])
    rows.append([InlineKeyboardButton(text=BUTTONS["back"], callback_data="editnav:back")])
    return InlineKeyboardMarkup(rows)


def build_edit_categories_inline_keyboard(*, selected_codes: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        mark = "✅ " if code in selected_codes else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"regcat:{code}")])
    rows.append([InlineKeyboardButton(text=BUTTONS["groups_done"], callback_data="regcat:done")])
    rows.append([InlineKeyboardButton(text=BUTTONS["back"], callback_data="editnav:back")])
    return InlineKeyboardMarkup(rows)
