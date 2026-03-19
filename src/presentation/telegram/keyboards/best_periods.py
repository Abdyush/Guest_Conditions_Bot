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
    rows.append([InlineKeyboardButton(text="Назад к группам", callback_data="nav:back_best_groups")])
    return InlineKeyboardMarkup(rows)


def build_best_period_result_inline_keyboard(*, category_idx: int, has_offer_text: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_offer_text:
        rows.append([InlineKeyboardButton(text="Текст специального предложения", callback_data=f"bestoff:{category_idx}")])
    rows.append([InlineKeyboardButton(text="Назад к категориям", callback_data="nav:back_best_categories")])
    return InlineKeyboardMarkup(rows)


def build_best_offer_text_inline_keyboard(*, category_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Назад к предложению", callback_data=f"bestres:{category_idx}")],
        ]
    )
