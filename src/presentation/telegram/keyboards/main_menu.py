from __future__ import annotations

from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.ui_texts import BANK_LABEL_TO_CODE, BUTTONS, CATEGORY_LABEL_TO_CODE, LOYALTY_OPTIONS


BEST_PERIOD_BUTTON = BUTTONS["best_period"]
PERIOD_QUOTES_BUTTON = BUTTONS["period_quotes"]
AVAILABLE_ROOMS_BUTTON = BUTTONS["available_rooms"]
EDIT_DATA_BUTTON = BUTTONS["edit_data"]
BACK_BUTTON = BUTTONS["back"]
CANCEL_BUTTON = BUTTONS["cancel"]
SHARE_PHONE_BUTTON = BUTTONS["share_phone"]

EDIT_ADULTS_BUTTON = BUTTONS["edit_adults"]
EDIT_CHILDREN_BUTTON = BUTTONS["edit_children"]
EDIT_INFANTS_BUTTON = BUTTONS["edit_infants"]
EDIT_GROUPS_BUTTON = BUTTONS["edit_groups"]
EDIT_LOYALTY_BUTTON = BUTTONS["edit_loyalty"]
EDIT_BANK_BUTTON = BUTTONS["edit_bank"]
EDIT_PRICE_BUTTON = BUTTONS["edit_price"]


def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=EDIT_DATA_BUTTON), KeyboardButton(text=AVAILABLE_ROOMS_BUTTON)],
            [KeyboardButton(text=PERIOD_QUOTES_BUTTON), KeyboardButton(text=BEST_PERIOD_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_edit_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=EDIT_ADULTS_BUTTON)],
            [KeyboardButton(text=EDIT_CHILDREN_BUTTON)],
            [KeyboardButton(text=EDIT_INFANTS_BUTTON)],
            [KeyboardButton(text=EDIT_GROUPS_BUTTON)],
            [KeyboardButton(text=EDIT_LOYALTY_BUTTON)],
            [KeyboardButton(text=EDIT_BANK_BUTTON)],
            [KeyboardButton(text=EDIT_PRICE_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SHARE_PHONE_BUTTON, request_contact=True)],
            [KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_categories_inline_keyboard(*, selected_codes: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        mark = "✅ " if code in selected_codes else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"regcat:{code}")])
    rows.append([InlineKeyboardButton(text=BUTTONS["groups_done"], callback_data="regcat:done")])
    return InlineKeyboardMarkup(rows)


def build_best_group_inline_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"bestgrp:{code}")])
    rows.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_main")])
    return InlineKeyboardMarkup(rows)


def build_best_period_details_inline_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_best_groups")]]
    return InlineKeyboardMarkup(rows)


def build_quotes_group_inline_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"qgrp:{code}")])
    rows.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_main")])
    return InlineKeyboardMarkup(rows)


def build_quotes_categories_inline_keyboard(*, category_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(category_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"qcat:{idx}")])
    rows.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_quotes_calendar")])
    return InlineKeyboardMarkup(rows)


def build_quotes_category_details_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_quotes_categories")]]
    )


def build_available_categories_inline_keyboard(*, category_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(category_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"availcat:{idx}")])
    rows.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_main")])
    return InlineKeyboardMarkup(rows)


def build_available_periods_inline_keyboard(*, category_idx: int, periods: list[tuple[date, date, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, (_, _, label) in enumerate(periods):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"availprd:{category_idx}:{idx}")])
    rows.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data="nav:back_avail_categories")])
    return InlineKeyboardMarkup(rows)


def build_available_period_details_inline_keyboard(*, category_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=BACK_BUTTON, callback_data=f"availcat:{category_idx}")]]
    )


def build_loyalty_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=LOYALTY_OPTIONS[0]), KeyboardButton(text=LOYALTY_OPTIONS[1]), KeyboardButton(text=LOYALTY_OPTIONS[2])],
            [KeyboardButton(text=LOYALTY_OPTIONS[3]), KeyboardButton(text=LOYALTY_OPTIONS[4]), KeyboardButton(text=LOYALTY_OPTIONS[5])],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_bank_keyboard() -> ReplyKeyboardMarkup:
    labels = list(BANK_LABEL_TO_CODE.keys())
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0])],
            [KeyboardButton(text=labels[1]), KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_numeric_edit_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK_BUTTON)]],
        resize_keyboard=True,
    )
