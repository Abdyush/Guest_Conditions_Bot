from __future__ import annotations

from enum import Enum


class ActiveFlow(str, Enum):
    AVAILABLE_ROOMS = "available_rooms"
    BEST_PERIODS = "best_periods"
    PERIOD_QUOTES = "period_quotes"
    REGISTRATION = "registration"
