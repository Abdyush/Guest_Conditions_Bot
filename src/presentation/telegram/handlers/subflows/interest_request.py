from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.keyboards.interest_request import (
    AVREQ_BACK_CALENDAR,
    AVREQ_BACK_DETAIL,
    AVREQ_BACK_PARENT,
    AVREQ_CONTACT_UNAVAILABLE,
    build_interest_request_calendar_inline_keyboard,
    build_interest_request_result_inline_keyboard,
    build_interest_request_tariff_inline_keyboard,
)
from src.presentation.telegram.presenters.booking_period import booking_coverage_end
from src.presentation.telegram.presenters.interest_request_presenter import (
    render_interest_request_calendar_prompt,
    render_interest_request_message,
    render_interest_request_tariff_prompt,
)
from src.presentation.telegram.state.session_store import InterestRequestDraft


@dataclass(frozen=True, slots=True)
class InterestRequestStartContext:
    source_kind: str
    category_name: str
    month_cursor: date
    period_mode: str = "select"
    checkin: date | None = None
    checkout: date | None = None
    quote_group_ids: list[str] | None = None
    source_group_id: str | None = None
    source_group_idx: int | None = None
    source_category_idx: int | None = None
    source_period_idx: int | None = None


class InterestRequestParentAdapter(Protocol):
    calendar_parent_back_text: str
    result_parent_back_text: str

    async def handle_missing_guest(self, *, telegram_user_id: int, query) -> None: ...

    async def resolve_start_context(
        self,
        *,
        guest_id: str,
        telegram_user_id: int,
        data: str,
    ) -> InterestRequestStartContext | None: ...

    async def show_source_screen(self, *, guest_id: str, telegram_user_id: int, query, draft: InterestRequestDraft) -> None: ...

    async def show_parent_screen(self, *, guest_id: str, telegram_user_id: int, query, draft: InterestRequestDraft | None) -> None: ...

    async def show_period_screen(self, *, guest_id: str, telegram_user_id: int, query, draft: InterestRequestDraft | None) -> None: ...


class InterestRequestSubflow:
    def __init__(self, *, deps: TelegramHandlersDependencies, adapter: InterestRequestParentAdapter):
        self._deps = deps
        self._adapter = adapter

    async def handle_callback(self, telegram_user_id: int, query, data: str) -> None:
        guest_id = self._deps.identity.resolve_guest_id(telegram_user_id=telegram_user_id)
        if not guest_id:
            await self._adapter.handle_missing_guest(telegram_user_id=telegram_user_id, query=query)
            return

        if data == AVREQ_CONTACT_UNAVAILABLE:
            await query.answer("\u041a\u043e\u043d\u0442\u0430\u043a\u0442 \u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0433\u043e \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d.", show_alert=True)
            return
        if data.startswith("avreq:start:"):
            await self._start(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if data.startswith("avreq:cal:"):
            await self._handle_calendar(telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if data.startswith("avreq:tariff:"):
            await self._handle_tariff(guest_id=guest_id, telegram_user_id=telegram_user_id, query=query, data=data)
            return
        if data == AVREQ_BACK_DETAIL:
            draft = await self._get_draft(telegram_user_id)
            if draft is None:
                await query.answer()
                return
            await self._adapter.show_source_screen(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
                draft=draft,
            )
            return
        if data == AVREQ_BACK_CALENDAR:
            session = await self._deps.sessions.get(telegram_user_id)
            draft = session.interest_request
            if draft is None:
                await query.answer()
                return
            if draft.period_mode == "fixed":
                session.interest_request = None
                await self._adapter.show_period_screen(
                    guest_id=guest_id,
                    telegram_user_id=telegram_user_id,
                    query=query,
                    draft=draft,
                )
                return
            draft.checkin = None
            draft.checkout = None
            await self._show_calendar(telegram_user_id=telegram_user_id, query=query)
            return
        if data == AVREQ_BACK_PARENT:
            session = await self._deps.sessions.get(telegram_user_id)
            draft = session.interest_request
            session.interest_request = None
            await self._adapter.show_parent_screen(
                guest_id=guest_id,
                telegram_user_id=telegram_user_id,
                query=query,
                draft=draft,
            )
            return

        await query.answer()

    async def _start(self, *, guest_id: str, telegram_user_id: int, query, data: str) -> None:
        start_context = await self._adapter.resolve_start_context(
            guest_id=guest_id,
            telegram_user_id=telegram_user_id,
            data=data,
        )
        if start_context is None:
            await query.answer()
            return

        session = await self._deps.sessions.get(telegram_user_id)
        session.interest_request = InterestRequestDraft(
            period_mode=start_context.period_mode,
            source_kind=start_context.source_kind,
            category_name=start_context.category_name,
            source_group_id=start_context.source_group_id,
            source_group_idx=start_context.source_group_idx,
            source_category_idx=start_context.source_category_idx,
            source_period_idx=start_context.source_period_idx,
            quote_group_ids=list(start_context.quote_group_ids) if start_context.quote_group_ids is not None else None,
            month_cursor=start_context.month_cursor,
            checkin=start_context.checkin,
            checkout=start_context.checkout,
            tariff=None,
            sent_to_admin=False,
        )
        if start_context.period_mode == "fixed" and start_context.checkin is not None and start_context.checkout is not None:
            await self._show_tariff(telegram_user_id=telegram_user_id, query=query)
            return
        await self._show_calendar(telegram_user_id=telegram_user_id, query=query)

    async def _handle_calendar(self, *, telegram_user_id: int, query, data: str) -> None:
        draft = await self._get_draft(telegram_user_id)
        if draft is None or draft.month_cursor is None:
            await query.answer()
            return

        if data == "avreq:cal:noop":
            await query.answer()
            return
        if data.startswith("avreq:cal:nav:"):
            try:
                draft.month_cursor = date.fromisoformat(data.split(":", 3)[3]).replace(day=1)
            except ValueError:
                await query.answer()
                return
            await query.answer()
            if query.message is not None:
                await query.edit_message_reply_markup(
                    reply_markup=build_interest_request_calendar_inline_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                        parent_back_text=self._adapter.calendar_parent_back_text,
                    )
                )
            return
        if not data.startswith("avreq:cal:day:"):
            await query.answer()
            return

        try:
            picked = date.fromisoformat(data.split(":", 3)[3])
        except ValueError:
            await query.answer()
            return

        if draft.checkin is None:
            draft.checkin = picked
            draft.checkout = None
            draft.month_cursor = picked.replace(day=1)
            await query.answer()
            if query.message is not None:
                await query.edit_message_reply_markup(
                    reply_markup=build_interest_request_calendar_inline_keyboard(
                        month_cursor=draft.month_cursor,
                        checkin=draft.checkin,
                        checkout=draft.checkout,
                        parent_back_text=self._adapter.calendar_parent_back_text,
                    )
                )
            return

        if draft.checkout is None:
            if picked <= draft.checkin:
                draft.checkin = picked
                draft.checkout = None
                draft.month_cursor = picked.replace(day=1)
                await query.answer()
                if query.message is not None:
                    await query.edit_message_reply_markup(
                        reply_markup=build_interest_request_calendar_inline_keyboard(
                            month_cursor=draft.month_cursor,
                            checkin=draft.checkin,
                            checkout=None,
                            parent_back_text=self._adapter.calendar_parent_back_text,
                        )
                    )
                return

            draft.checkout = picked
            await self._show_tariff(telegram_user_id=telegram_user_id, query=query)
            return

        await query.answer()

    async def _handle_tariff(self, *, guest_id: str, telegram_user_id: int, query, data: str) -> None:
        draft = await self._get_draft(telegram_user_id)
        if draft is None or draft.checkin is None or draft.checkout is None or not draft.category_name:
            await query.answer()
            return

        tariff_code = data.split(":", 2)[2].strip().lower()
        if tariff_code not in {"breakfast", "fullpansion"}:
            await query.answer()
            return
        draft.tariff = tariff_code
        draft.sent_to_admin = False

        profile = self._deps.profile.get_guest_profile(guest_id=guest_id)
        if profile is None:
            await self._adapter.handle_missing_guest(telegram_user_id=telegram_user_id, query=query)
            return

        open_price_minor, preliminary_price_minor, loyalty_status, special_offers = self._resolve_quote_summary(
            guest_id=guest_id,
            category_name=draft.category_name,
            period_start=draft.checkin,
            period_end=draft.checkout,
            tariff=tariff_code,
            quote_group_ids=draft.quote_group_ids,
        )

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_interest_request_message(
                    category_name=draft.category_name,
                    period_start=draft.checkin,
                    period_end=draft.checkout,
                    tariff_name=tariff_code,
                    open_price_minor=open_price_minor,
                    preliminary_price_minor=preliminary_price_minor,
                    adults=profile.occupancy.adults,
                    children_4_13=profile.occupancy.children_4_13,
                    infants_0_3=profile.occupancy.infants,
                    loyalty_status=loyalty_status,
                    special_offers=special_offers,
                ),
                reply_markup=build_interest_request_result_inline_keyboard(
                    parent_back_text=self._adapter.result_parent_back_text,
                    contact_url=self._responsible_contact_url(),
                ),
            )

    async def _show_calendar(self, *, telegram_user_id: int, query) -> None:
        draft = await self._get_draft(telegram_user_id)
        if draft is None or draft.month_cursor is None or not draft.category_name:
            await query.answer()
            return

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_interest_request_calendar_prompt(category_name=draft.category_name),
                reply_markup=build_interest_request_calendar_inline_keyboard(
                    month_cursor=draft.month_cursor,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                    parent_back_text=self._adapter.calendar_parent_back_text,
                ),
            )

    async def _show_tariff(self, *, telegram_user_id: int, query) -> None:
        draft = await self._get_draft(telegram_user_id)
        if draft is None or draft.checkin is None or draft.checkout is None or not draft.category_name:
            await query.answer()
            return

        await query.answer()
        if query.message is not None:
            await query.edit_message_text(
                render_interest_request_tariff_prompt(
                    category_name=draft.category_name,
                    checkin=draft.checkin,
                    checkout=draft.checkout,
                ),
                reply_markup=build_interest_request_tariff_inline_keyboard(
                    parent_back_text=self._adapter.result_parent_back_text,
                ),
            )

    async def _get_draft(self, telegram_user_id: int) -> InterestRequestDraft | None:
        session = await self._deps.sessions.get(telegram_user_id)
        return session.interest_request

    def _resolve_quote_summary(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariff: str,
        quote_group_ids: list[str] | None,
    ) -> tuple[int | None, int | None, str | None, list[tuple[date, date, str]]]:
        _, quotes = self._deps.period_quotes.get_period_quotes(
            guest_id=guest_id,
            period_start=period_start,
            period_end=booking_coverage_end(period_end),
            group_ids=set(quote_group_ids) if quote_group_ids else None,
        )
        matching_quotes = [
            quote
            for quote in quotes
            if quote.category_name == category_name and quote.tariff.strip().lower() == tariff
        ]
        if not matching_quotes:
            return None, None, None, []

        open_price_minor = sum(quote.total_old_minor for quote in matching_quotes)
        preliminary_price_minor = sum(quote.total_new_minor for quote in matching_quotes)
        loyalty_status = next((quote.loyalty_status for quote in matching_quotes if quote.loyalty_status), None)

        special_offers: list[tuple[date, date, str]] = []
        seen_offers: set[tuple[date, date, str]] = set()
        for quote in matching_quotes:
            if not quote.offer_title:
                continue
            offer_key = (quote.applied_from, quote.applied_to, quote.offer_title)
            if offer_key in seen_offers:
                continue
            seen_offers.add(offer_key)
            special_offers.append(offer_key)

        return open_price_minor, preliminary_price_minor, loyalty_status, special_offers

    def _responsible_contact_url(self) -> str | None:
        if self._deps.admin_telegram_id is None:
            return None
        return f"tg://user?id={self._deps.admin_telegram_id}"
