from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON


def build_available_groups_inline_keyboard(*, group_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(group_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"availcat:grp:{idx}")])
    return InlineKeyboardMarkup(rows)


def build_available_categories_inline_keyboard(*, group_idx: int, category_names: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, name in enumerate(category_names):
        rows.append([InlineKeyboardButton(text=name, callback_data=f"availcat:cat:{group_idx}:{idx}")])
    rows.append([InlineKeyboardButton(text="Назад к группам", callback_data="nav:back_avail_categories")])
    return InlineKeyboardMarkup(rows)


def build_available_periods_inline_keyboard(*, group_idx: int, category_idx: int, periods: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for idx, label in enumerate(periods):
        rows.append([InlineKeyboardButton(text=label, callback_data=f"availprd:detail:{group_idx}:{category_idx}:{idx}")])
    rows.append([InlineKeyboardButton(text="Назад к категориям", callback_data=f"availcat:grp:{group_idx}")])
    return InlineKeyboardMarkup(rows)


def build_available_period_details_inline_keyboard(
    *,
    group_idx: int,
    category_idx: int,
    period_idx: int,
    has_offer_text: bool,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_offer_text:
        rows.append([InlineKeyboardButton(text="Текст специального предложения", callback_data=f"avoff:{group_idx}:{category_idx}:{period_idx}")])
    rows.append([InlineKeyboardButton(text="Назад к периодам", callback_data=f"availprd:list:{group_idx}:{category_idx}")])
    return InlineKeyboardMarkup(rows)


def build_available_offer_text_inline_keyboard(*, group_idx: int, category_idx: int, period_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Назад к предложению", callback_data=f"availprd:detail:{group_idx}:{category_idx}:{period_idx}")],
        ]
    )


def build_available_scenario_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )

