from __future__ import annotations

import calendar
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


MONTH_NAMES_RU = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]
WEEKDAY_SHORT_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def shift_month(d: date, delta: int) -> date:
    month_index = d.month - 1 + delta
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def build_period_calendar_keyboard(
    *,
    month_cursor: date,
    checkin: date | None,
    checkout: date | None,
    callback_prefix: str = "cal",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    noop_data = f"{callback_prefix}:noop"
    month_title = f"{MONTH_NAMES_RU[month_cursor.month - 1]} {month_cursor.year}"
    rows.append([InlineKeyboardButton(text=month_title, callback_data=noop_data)])
    rows.append([InlineKeyboardButton(text=x, callback_data=noop_data) for x in WEEKDAY_SHORT_RU])

    cal = calendar.Calendar(firstweekday=0)
    for week in cal.monthdayscalendar(month_cursor.year, month_cursor.month):
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data=noop_data))
                continue
            day_date = date(month_cursor.year, month_cursor.month, day)
            row.append(
                InlineKeyboardButton(
                    text=_render_day_text(day_date, checkin=checkin, checkout=checkout),
                    callback_data=f"{callback_prefix}:day:{day_date.isoformat()}",
                )
            )
        rows.append(row)

    prev_month = shift_month(month_cursor, -1).isoformat()
    next_month = shift_month(month_cursor, 1).isoformat()
    rows.append(
        [
            InlineKeyboardButton(text="«", callback_data=f"{callback_prefix}:nav:{prev_month}"),
            InlineKeyboardButton(text="»", callback_data=f"{callback_prefix}:nav:{next_month}"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _render_day_text(day_date: date, *, checkin: date | None, checkout: date | None) -> str:
    d = str(day_date.day)
    if checkin is None:
        return d
    if checkout is None:
        if day_date == checkin:
            return f"[{d}]"
        return d
    if day_date == checkin or day_date == checkout:
        return f"[{d}]"
    if checkin < day_date < checkout:
        return f"({d})"
    return d
