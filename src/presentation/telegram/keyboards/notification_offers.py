from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.callbacks.data_parser import NAV_BACK_NOTIFICATION_GROUPS, NAV_MAIN
from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON


def build_notification_scenario_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )


def build_notification_groups_inline_keyboard(*, run_id: str, group_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(group_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"ntfgrp:{run_id}:{idx}")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=NAV_MAIN)])
    return InlineKeyboardMarkup(rows)


def build_notification_categories_inline_keyboard(*, run_id: str, group_idx: int, category_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(category_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"ntfcat:{run_id}:{group_idx}:{idx}")])
    rows.append([InlineKeyboardButton(text="Назад к группам", callback_data=f"{NAV_BACK_NOTIFICATION_GROUPS}:{run_id}")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=NAV_MAIN)])
    return InlineKeyboardMarkup(rows)


def build_notification_periods_inline_keyboard(*, run_id: str, group_idx: int, category_idx: int, periods: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, label in enumerate(periods):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"ntfprd:{run_id}:{group_idx}:{category_idx}:{idx}")])
    rows.append([InlineKeyboardButton(text="Назад к категориям", callback_data=f"ntfgrp:{run_id}:{group_idx}")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=NAV_MAIN)])
    return InlineKeyboardMarkup(rows)


def build_notification_period_details_inline_keyboard(
    *,
    run_id: str,
    group_idx: int,
    category_idx: int,
    period_idx: int,
    has_offer_text: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_offer_text:
        rows.append([InlineKeyboardButton(text="Текст специального предложения", callback_data=f"ntfoff:{run_id}:{group_idx}:{category_idx}:{period_idx}")])
    rows.append([InlineKeyboardButton(text="Назад к периодам", callback_data=f"ntfcat:{run_id}:{group_idx}:{category_idx}")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data=NAV_MAIN)])
    return InlineKeyboardMarkup(rows)


def build_notification_offer_text_inline_keyboard(*, run_id: str, group_idx: int, category_idx: int, period_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Назад к предложению", callback_data=f"ntfprd:{run_id}:{group_idx}:{category_idx}:{period_idx}")],
            [InlineKeyboardButton(text="Главное меню", callback_data=NAV_MAIN)],
        ]
    )
