from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage

from src.application.dto.period_quote import PeriodQuote
from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.fsm_states import FSM_TO_STATE, STATE_TO_FSM


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
    run_id: str | None = None
    quotes: list[PeriodQuote] | None = None
    category_names: list[str] | None = None
    last_room_dates_by_category: dict[str, list[date]] | None = None


@dataclass(slots=True)
class BestPeriodDraft:
    group_id: str | None = None
    category_names: list[str] | None = None


@dataclass(slots=True)
class UserSession:
    state: ConversationState = ConversationState.IDLE
    active_flow: ActiveFlow | None = None
    registration: RegistrationDraft | None = None
    best_period: BestPeriodDraft | None = None
    period_quotes: PeriodQuotesDraft | None = None
    available_category_names: list[str] | None = None
    available_category_rows: list | None = None


class InMemorySessionStore:
    """
    Backward-compatible name: actual implementation stores FSM state/data in Redis via aiogram storage.
    """

    def __init__(self, *, storage: RedisStorage):
        self._storage = storage
        self._cache: dict[int, UserSession] = {}

    async def get(self, telegram_user_id: int) -> UserSession:
        cached = self._cache.get(telegram_user_id)
        if cached is not None:
            return cached

        key = self._build_key(telegram_user_id)
        fsm = FSMContext(storage=self._storage, key=key)
        state_raw = await fsm.get_state()
        data = await fsm.get_data()

        session = UserSession(
            state=self._to_conversation_state(state_raw),
            active_flow=self._deserialize_active_flow(data.get("active_flow")),
            registration=self._deserialize_registration(data.get("registration")),
            best_period=self._deserialize_best_period(data.get("best_period")),
            period_quotes=self._deserialize_period_quotes(data.get("period_quotes")),
            available_category_names=self._deserialize_available_category_names(data.get("available_category_names")),
            available_category_rows=None,
        )
        self._cache[telegram_user_id] = session
        return session

    async def set_state(self, telegram_user_id: int, state: ConversationState) -> None:
        session = await self.get(telegram_user_id)
        session.state = state
        await self.persist(telegram_user_id)

    async def reset(self, telegram_user_id: int) -> None:
        session = UserSession()
        self._cache[telegram_user_id] = session
        await self.persist(telegram_user_id)

    async def persist(self, telegram_user_id: int) -> None:
        session = self._cache.get(telegram_user_id)
        if session is None:
            return
        key = self._build_key(telegram_user_id)
        fsm_state = STATE_TO_FSM.get(session.state, STATE_TO_FSM[ConversationState.IDLE]).state
        fsm = FSMContext(storage=self._storage, key=key)
        await fsm.set_state(fsm_state)
        await fsm.set_data(
            {
                "active_flow": self._serialize_active_flow(session.active_flow),
                "registration": self._serialize_registration(session.registration),
                "best_period": self._serialize_best_period(session.best_period),
                "period_quotes": self._serialize_period_quotes(session.period_quotes),
                "available_category_names": self._serialize_available_category_names(session.available_category_names),
            },
        )

    async def close(self) -> None:
        await self._storage.close()

    async def flush_all(self) -> None:
        for telegram_user_id in list(self._cache.keys()):
            await self.persist(telegram_user_id)

    @staticmethod
    def _build_key(telegram_user_id: int) -> StorageKey:
        return StorageKey(bot_id=0, chat_id=telegram_user_id, user_id=telegram_user_id)

    @staticmethod
    def _to_conversation_state(value: str | None) -> ConversationState:
        if not value:
            return ConversationState.IDLE
        return FSM_TO_STATE.get(value, ConversationState.IDLE)

    @staticmethod
    def _serialize_registration(draft: RegistrationDraft | None) -> dict | None:
        if draft is None:
            return None
        return {
            "phone": draft.phone,
            "name": draft.name,
            "adults": draft.adults,
            "children_4_13": draft.children_4_13,
            "infants_0_3": draft.infants_0_3,
            "allowed_groups": sorted(draft.allowed_groups) if draft.allowed_groups is not None else None,
            "loyalty_status": draft.loyalty_status,
            "bank_status": draft.bank_status,
            "desired_price_rub": str(draft.desired_price_rub) if draft.desired_price_rub is not None else None,
        }

    @staticmethod
    def _deserialize_registration(payload) -> RegistrationDraft | None:
        if not payload:
            return None
        desired = payload.get("desired_price_rub")
        allowed = payload.get("allowed_groups")
        return RegistrationDraft(
            phone=payload.get("phone"),
            name=payload.get("name"),
            adults=payload.get("adults"),
            children_4_13=payload.get("children_4_13"),
            infants_0_3=payload.get("infants_0_3"),
            allowed_groups=set(allowed) if allowed else None,
            loyalty_status=payload.get("loyalty_status"),
            bank_status=payload.get("bank_status"),
            desired_price_rub=Decimal(str(desired)) if desired is not None else None,
        )

    @staticmethod
    def _serialize_period_quotes(draft: PeriodQuotesDraft | None) -> dict | None:
        if draft is None:
            return None
        return {
            "group_id": draft.group_id,
            "month_cursor": draft.month_cursor.isoformat() if draft.month_cursor else None,
            "checkin": draft.checkin.isoformat() if draft.checkin else None,
            "checkout": draft.checkout.isoformat() if draft.checkout else None,
            "run_id": draft.run_id,
            "quotes": [_serialize_period_quote(q) for q in (draft.quotes or [])],
            "category_names": list(draft.category_names) if draft.category_names is not None else None,
            "last_room_dates_by_category": {
                k: [x.isoformat() for x in v] for k, v in (draft.last_room_dates_by_category or {}).items()
            }
            if draft.last_room_dates_by_category is not None
            else None,
        }

    @staticmethod
    def _serialize_best_period(draft: BestPeriodDraft | None) -> dict | None:
        if draft is None:
            return None
        return {
            "group_id": draft.group_id,
            "category_names": list(draft.category_names) if draft.category_names is not None else None,
        }

    @staticmethod
    def _deserialize_best_period(payload) -> BestPeriodDraft | None:
        if not payload:
            return None
        return BestPeriodDraft(
            group_id=payload.get("group_id"),
            category_names=list(payload["category_names"]) if payload.get("category_names") is not None else None,
        )

    @staticmethod
    def _deserialize_period_quotes(payload) -> PeriodQuotesDraft | None:
        if not payload:
            return None
        dates_map_raw = payload.get("last_room_dates_by_category")
        return PeriodQuotesDraft(
            group_id=payload.get("group_id"),
            month_cursor=date.fromisoformat(payload["month_cursor"]) if payload.get("month_cursor") else None,
            checkin=date.fromisoformat(payload["checkin"]) if payload.get("checkin") else None,
            checkout=date.fromisoformat(payload["checkout"]) if payload.get("checkout") else None,
            run_id=payload.get("run_id"),
            quotes=[_deserialize_period_quote(x) for x in (payload.get("quotes") or [])],
            category_names=list(payload["category_names"]) if payload.get("category_names") is not None else None,
            last_room_dates_by_category={
                key: [date.fromisoformat(x) for x in values]
                for key, values in (dates_map_raw or {}).items()
            }
            if dates_map_raw is not None
            else None,
        )

    @staticmethod
    def _serialize_available_category_names(value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return list(value)

    @staticmethod
    def _serialize_active_flow(value: ActiveFlow | None) -> str | None:
        if value is None:
            return None
        return value.value

    @staticmethod
    def _deserialize_active_flow(value: str | None) -> ActiveFlow | None:
        if value is None:
            return None
        try:
            return ActiveFlow(value)
        except ValueError:
            return None

    @staticmethod
    def _deserialize_available_category_names(value) -> list[str] | None:
        if value is None:
            return None
        return list(value)


def _serialize_period_quote(quote: PeriodQuote) -> dict:
    return {
        "category_name": quote.category_name,
        "group_id": quote.group_id,
        "tariff": quote.tariff,
        "from_date": quote.from_date.isoformat(),
        "to_date": quote.to_date.isoformat(),
        "applied_from": quote.applied_from.isoformat(),
        "applied_to": quote.applied_to.isoformat(),
        "nights": quote.nights,
        "total_old_minor": quote.total_old_minor,
        "total_new_minor": quote.total_new_minor,
        "offer_id": quote.offer_id,
        "offer_title": quote.offer_title,
        "offer_repr": quote.offer_repr,
        "loyalty_status": quote.loyalty_status,
        "loyalty_percent": quote.loyalty_percent,
        "bank_status": quote.bank_status,
        "bank_percent": quote.bank_percent,
    }


def _deserialize_period_quote(payload: dict) -> PeriodQuote:
    return PeriodQuote(
        category_name=payload["category_name"],
        group_id=payload["group_id"],
        tariff=payload["tariff"],
        from_date=date.fromisoformat(payload["from_date"]),
        to_date=date.fromisoformat(payload["to_date"]),
        applied_from=date.fromisoformat(payload["applied_from"]),
        applied_to=date.fromisoformat(payload["applied_to"]),
        nights=int(payload["nights"]),
        total_old_minor=int(payload["total_old_minor"]),
        total_new_minor=int(payload["total_new_minor"]),
        offer_id=payload.get("offer_id"),
        offer_title=payload.get("offer_title"),
        offer_repr=payload.get("offer_repr"),
        loyalty_status=payload.get("loyalty_status"),
        loyalty_percent=payload.get("loyalty_percent"),
        bank_status=payload.get("bank_status"),
        bank_percent=payload.get("bank_percent"),
    )
