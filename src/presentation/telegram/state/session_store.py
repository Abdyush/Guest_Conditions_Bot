from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.presentation.telegram.state.conversation_state import ConversationState


@dataclass(slots=True)
class RegistrationDraft:
    phone: str | None = None
    name: str | None = None
    adults: int | None = None
    children_4_13: int | None = None
    infants_0_3: int | None = None
    allowed_groups: set[str] | None = None
    loyalty_status: str | None = None
    bank_status: str | None = None
    desired_price_rub: Decimal | None = None


@dataclass(slots=True)
class PeriodQuotesDraft:
    group_id: str | None = None
    month_cursor: date | None = None
    checkin: date | None = None
    checkout: date | None = None


@dataclass(slots=True)
class UserSession:
    state: ConversationState = ConversationState.IDLE
    registration: RegistrationDraft | None = None
    period_quotes: PeriodQuotesDraft | None = None
    available_category_names: list[str] | None = None


class InMemorySessionStore:
    def __init__(self):
        self._sessions: dict[int, UserSession] = {}

    def get(self, telegram_user_id: int) -> UserSession:
        return self._sessions.setdefault(telegram_user_id, UserSession())

    def set_state(self, telegram_user_id: int, state: ConversationState) -> None:
        session = self.get(telegram_user_id)
        session.state = state

    def reset(self, telegram_user_id: int) -> None:
        session = self.get(telegram_user_id)
        session.state = ConversationState.IDLE
        session.registration = None
        session.period_quotes = None
        session.available_category_names = None
