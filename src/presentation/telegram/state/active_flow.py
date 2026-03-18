from __future__ import annotations

from enum import Enum


class ActiveFlow(str, Enum):
    ADMIN_MENU = "admin_menu"
    AVAILABLE_ROOMS = "available_rooms"
    BEST_PERIODS = "best_periods"
    NOTIFICATION_OFFERS = "notification_offers"
    PERIOD_QUOTES = "period_quotes"
    REGISTRATION = "registration"
