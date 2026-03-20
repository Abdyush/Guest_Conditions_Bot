from __future__ import annotations

from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.presentation.telegram.keyboards.calendar_picker import build_period_calendar_keyboard
from src.presentation.telegram.keyboards.main_menu import MAIN_MENU_BUTTON


AVREQ_CONTACT_UNAVAILABLE = "avreq:contact"


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
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Заинтересовало", callback_data=f"avreq:start:{group_idx}:{category_idx}:{period_idx}")]
    ]
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



def build_available_request_calendar_inline_keyboard(
    *,
    month_cursor: date,
    checkin: date | None,
    checkout: date | None,
    group_idx: int,
) -> InlineKeyboardMarkup:
    keyboard = build_period_calendar_keyboard(
        month_cursor=month_cursor,
        checkin=checkin,
        checkout=checkout,
        callback_prefix="avreq:cal",
    )
    rows = [list(row) for row in keyboard.inline_keyboard]
    rows.append([InlineKeyboardButton(text="Назад к предложению", callback_data="avreq:back:detail")])
    rows.append([InlineKeyboardButton(text="Назад к категориям", callback_data=f"avreq:back:categories:{group_idx}")])
    return InlineKeyboardMarkup(rows)



def build_available_request_tariff_inline_keyboard(*, group_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Только завтраки", callback_data="avreq:tariff:breakfast")],
            [InlineKeyboardButton(text="Полный пансион", callback_data="avreq:tariff:fullpansion")],
            [InlineKeyboardButton(text="Назад к выбору периода", callback_data="avreq:back:calendar")],
            [InlineKeyboardButton(text="Назад к выбору категорий", callback_data=f"avreq:back:categories:{group_idx}")],
        ]
    )



def build_available_request_result_inline_keyboard(*, group_idx: int, contact_url: str | None) -> InlineKeyboardMarkup:
    contact_button = (
        InlineKeyboardButton(text="Написать Никите", url=contact_url)
        if contact_url
        else InlineKeyboardButton(text="Написать Никите", callback_data=AVREQ_CONTACT_UNAVAILABLE)
    )
    return InlineKeyboardMarkup(
        [
            [contact_button],
            [InlineKeyboardButton(text="Назад к выбору периода", callback_data="avreq:back:calendar")],
            [InlineKeyboardButton(text="Назад к выбору категорий", callback_data=f"avreq:back:categories:{group_idx}")],
        ]
    )



def build_available_scenario_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MAIN_MENU_BUTTON)]],
        resize_keyboard=True,
    )

