from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.calendar_picker import build_period_calendar_keyboard
from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON
from src.presentation.telegram.ui_texts import CATEGORY_LABEL_TO_CODE


def build_period_quotes_scenario_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )


def build_period_quotes_groups_inline_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"qgrp:{code}")])
    return InlineKeyboardMarkup(rows)


def build_period_quotes_calendar_inline_keyboard(*, month_cursor, checkin, checkout) -> InlineKeyboardMarkup:
    base = build_period_calendar_keyboard(month_cursor=month_cursor, checkin=checkin, checkout=checkout)
    rows = [list(row) for row in base.inline_keyboard]
    rows.append([InlineKeyboardButton(text="Назад к группам", callback_data="nav:back_quotes_group")])
    return InlineKeyboardMarkup(rows)


def build_period_quotes_categories_inline_keyboard(*, category_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(category_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"qcat:{idx}")])
    rows.append([InlineKeyboardButton(text="Назад к датам", callback_data="nav:back_quotes_calendar")])
    return InlineKeyboardMarkup(rows)


def build_period_quotes_result_inline_keyboard(*, category_idx: int, has_offer_text: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_offer_text:
        rows.append([InlineKeyboardButton(text="Текст специального предложения", callback_data=f"qoff:{category_idx}")])
    rows.append([InlineKeyboardButton(text="Назад к категориям", callback_data="nav:back_quotes_categories")])
    return InlineKeyboardMarkup(rows)


def build_period_quotes_offer_text_inline_keyboard(*, category_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Назад к предложению", callback_data=f"qres:{category_idx}")],
        ]
    )


def build_period_quotes_empty_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Назад к датам", callback_data="nav:back_quotes_calendar")],
        ]
    )
