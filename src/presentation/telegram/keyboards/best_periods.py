from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON
from src.presentation.telegram.ui_texts import CATEGORY_LABEL_TO_CODE


def build_best_periods_scenario_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )


def build_best_groups_inline_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for label, code in CATEGORY_LABEL_TO_CODE.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"bestgrp:{code}")])
    return InlineKeyboardMarkup(rows)


def build_best_categories_inline_keyboard(*, category_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(category_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"bestcat:{idx}")])
    rows.append([InlineKeyboardButton(text="\u041d\u0430\u0437\u0430\u0434 \u043a \u0433\u0440\u0443\u043f\u043f\u0430\u043c", callback_data="nav:back_best_groups")])
    return InlineKeyboardMarkup(rows)


def build_best_period_result_inline_keyboard(
    *,
    category_idx: int,
    has_offer_text: bool,
    interest_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if interest_callback_data:
        rows.append([InlineKeyboardButton(text="\u0417\u0430\u0438\u043d\u0442\u0435\u0440\u0435\u0441\u043e\u0432\u0430\u043b\u043e", callback_data=interest_callback_data)])
    if has_offer_text:
        rows.append([InlineKeyboardButton(text="\u0422\u0435\u043a\u0441\u0442 \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044f", callback_data=f"bestoff:{category_idx}")])
    rows.append([InlineKeyboardButton(text="\u041d\u0430\u0437\u0430\u0434 \u043a \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f\u043c", callback_data="nav:back_best_categories")])
    return InlineKeyboardMarkup(rows)


def build_best_offer_text_inline_keyboard(*, category_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="\u041d\u0430\u0437\u0430\u0434 \u043a \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044e", callback_data=f"bestres:{category_idx}")],
        ]
    )
