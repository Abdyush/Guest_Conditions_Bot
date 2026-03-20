from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.presentation.telegram.keyboards.calendar_picker import build_period_calendar_keyboard


AVREQ_CONTACT_UNAVAILABLE = "avreq:contact"
AVREQ_BACK_DETAIL = "avreq:back:detail"
AVREQ_BACK_CALENDAR = "avreq:back:calendar"
AVREQ_BACK_PARENT = "avreq:back:parent"
AVREQ_TARIFF_BREAKFAST = "avreq:tariff:breakfast"
AVREQ_TARIFF_FULL_PANSION = "avreq:tariff:fullpansion"


def build_interest_request_calendar_inline_keyboard(
    *,
    month_cursor,
    checkin,
    checkout,
    parent_back_text: str,
) -> InlineKeyboardMarkup:
    keyboard = build_period_calendar_keyboard(
        month_cursor=month_cursor,
        checkin=checkin,
        checkout=checkout,
        callback_prefix="avreq:cal",
    )
    rows = [list(row) for row in keyboard.inline_keyboard]
    rows.append([InlineKeyboardButton(text="\u041d\u0430\u0437\u0430\u0434 \u043a \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044e", callback_data=AVREQ_BACK_DETAIL)])
    rows.append([InlineKeyboardButton(text=parent_back_text, callback_data=AVREQ_BACK_PARENT)])
    return InlineKeyboardMarkup(rows)


def build_interest_request_tariff_inline_keyboard(*, parent_back_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="\u0422\u043e\u043b\u044c\u043a\u043e \u0437\u0430\u0432\u0442\u0440\u0430\u043a\u0438", callback_data=AVREQ_TARIFF_BREAKFAST)],
            [InlineKeyboardButton(text="\u041f\u043e\u043b\u043d\u044b\u0439 \u043f\u0430\u043d\u0441\u0438\u043e\u043d", callback_data=AVREQ_TARIFF_FULL_PANSION)],
            [InlineKeyboardButton(text="\u041d\u0430\u0437\u0430\u0434 \u043a \u0432\u044b\u0431\u043e\u0440\u0443 \u043f\u0435\u0440\u0438\u043e\u0434\u0430", callback_data=AVREQ_BACK_CALENDAR)],
            [InlineKeyboardButton(text=parent_back_text, callback_data=AVREQ_BACK_PARENT)],
        ]
    )


def build_interest_request_result_inline_keyboard(*, parent_back_text: str, contact_url: str | None) -> InlineKeyboardMarkup:
    contact_button = (
        InlineKeyboardButton(text="\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u041d\u0438\u043a\u0438\u0442\u0435", url=contact_url)
        if contact_url
        else InlineKeyboardButton(text="\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u044c \u041d\u0438\u043a\u0438\u0442\u0435", callback_data=AVREQ_CONTACT_UNAVAILABLE)
    )
    return InlineKeyboardMarkup(
        [
            [contact_button],
            [InlineKeyboardButton(text="\u041d\u0430\u0437\u0430\u0434 \u043a \u0432\u044b\u0431\u043e\u0440\u0443 \u043f\u0435\u0440\u0438\u043e\u0434\u0430", callback_data=AVREQ_BACK_CALENDAR)],
            [InlineKeyboardButton(text=parent_back_text, callback_data=AVREQ_BACK_PARENT)],
        ]
    )
