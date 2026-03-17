from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.application.dto.get_best_period_query import GetBestPeriodQuery
from src.application.dto.get_period_quotes_query import GetPeriodQuotesQuery
from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote
from src.application.use_cases.calculate_matches_for_all_guests import CalculateMatchesForAllGuests
from src.application.use_cases.find_best_period_for_category import find_best_period_for_category
from src.application.use_cases.find_group_categories_for_guest import find_group_categories_for_guest
from src.application.use_cases.get_best_periods_for_guest_in_group import GetBestPeriodsForGuestInGroup
from src.application.use_cases.get_period_quotes_from_matches_run import GetPeriodQuotesFromMatchesRun
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.category_capacity import Occupancy
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext
from src.domain.services.pricing_service import PricingService
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money
from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_desired_matches_run_repository import PostgresDesiredMatchesRunRepository
from src.infrastructure.repositories.postgres_guests_repository import PostgresGuestsRepository
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository
from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository
from src.infrastructure.synchronization.recalculation_run_coordinator import RecalculationRunCoordinator


@dataclass(frozen=True, slots=True)
class GuestNotificationTarget:
    guest_id: str
    guest_name: str
    telegram_user_ids: list[int]
    category_names: list[str]


logger = logging.getLogger(__name__)


class TelegramUseCasesAdapter:
    _recalculation_coordinator: RecalculationRunCoordinator | None = None

    def __init__(self):
        self._identities_repo = PostgresUserIdentitiesRepository()
        self._guests_repo = PostgresGuestsRepository()
        self._rates_repo = PostgresDailyRatesRepository()
        self._offers_repo = PostgresOffersRepository()
        self._rules_repo = PostgresRulesRepository()
        self._matches_run_repo = PostgresMatchesRunRepository()
        self._desired_matches_run_repo = PostgresDesiredMatchesRunRepository()
        self._best_periods_uc = GetBestPeriodsForGuestInGroup(
            rates_repo=self._rates_repo,
            offers_repo=self._offers_repo,
            guests_repo=self._guests_repo,
            rules_repo=self._rules_repo,
        )
        self._period_quotes_uc = GetPeriodQuotesFromMatchesRun(self._matches_run_repo)
        if TelegramUseCasesAdapter._recalculation_coordinator is None:
            lock_key = int(os.getenv("RECALC_ADVISORY_LOCK_KEY", "90412031"))
            TelegramUseCasesAdapter._recalculation_coordinator = RecalculationRunCoordinator(
                advisory_lock_key=lock_key
            )

    @staticmethod
    def _provider() -> str:
        return "telegram"

    def resolve_guest_id(self, *, telegram_user_id: int) -> str | None:
        return self._identities_repo.resolve_guest_id(
            provider=self._provider(),
            external_user_id=str(telegram_user_id),
        )

    def unbind_telegram(self, *, telegram_user_id: int) -> None:
        self._identities_repo.delete_identity(
            provider=self._provider(),
            external_user_id=str(telegram_user_id),
        )

    def bind_guest_id(self, *, telegram_user_id: int, guest_id: str) -> bool:
        normalized_guest_id = guest_id.strip()
        if not normalized_guest_id:
            return False
        guests = self._guests_repo.get_active_guests()
        if not any(g.guest_id == normalized_guest_id for g in guests):
            return False

        self._identities_repo.upsert_identity(
            provider=self._provider(),
            external_user_id=str(telegram_user_id),
            guest_id=normalized_guest_id,
        )
        return True

    def bind_by_phone(self, *, telegram_user_id: int, phone: str) -> str | None:
        guest_id = self._identities_repo.resolve_guest_id(
            provider="phone",
            external_user_id=phone,
        )
        if not guest_id:
            return None
        guests = self._guests_repo.get_active_guests()
        if not any(g.guest_id == guest_id for g in guests):
            # Stale phone mapping: identity exists, but guest profile is absent.
            self._identities_repo.delete_identity(provider="phone", external_user_id=phone)
            return None
        self._identities_repo.upsert_identity(
            provider=self._provider(),
            external_user_id=str(telegram_user_id),
            guest_id=guest_id,
        )
        return guest_id

    def register_guest_by_phone(
        self,
        *,
        telegram_user_id: int,
        phone: str,
        name: str,
        adults: int,
        children_4_13: int,
        infants_0_3: int,
        allowed_groups: set[str],
        loyalty_status: str,
        bank_status: str | None,
        desired_price_rub: Decimal,
    ) -> str:
        loyalty_obj: LoyaltyStatus | None = LoyaltyStatus(loyalty_status.lower())
        bank = BankStatus(bank_status) if bank_status else None
        if bank is not None:
            loyalty_obj = None

        desired_minor = int((desired_price_rub * Decimal("100")).to_integral_value())
        guest = GuestPreferences(
            desired_price_per_night=Money.from_minor(desired_minor, currency="RUB"),
            loyalty_status=loyalty_obj,
            bank_status=bank,
            allowed_groups={x.strip().upper() for x in allowed_groups if x.strip()},
            occupancy=Occupancy(adults=adults, children_4_13=children_4_13, infants=infants_0_3),
            guest_name=name.strip(),
            guest_phone=phone,
        )
        guest_id = self._guests_repo.create_guest(guest)
        self._identities_repo.upsert_identity(provider="phone", external_user_id=phone, guest_id=guest_id)
        self._identities_repo.upsert_identity(
            provider=self._provider(),
            external_user_id=str(telegram_user_id),
            guest_id=guest_id,
        )
        self.recalculate_matches(trigger=f"registration:{telegram_user_id}")
        return guest_id

    def recalculate_matches(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        booking_date: date | None = None,
        trigger: str = "direct",
    ) -> str:
        today = date.today()
        actual_date_from = date_from or today
        actual_date_to = date_to or (today + timedelta(days=90))
        actual_booking_date = booking_date or today

        loyalty_policy = LoyaltyPolicy(
            {
                LoyaltyStatus.WHITE: Decimal("0.05"),
                LoyaltyStatus.BRONZE: Decimal("0.07"),
                LoyaltyStatus.SILVER: Decimal("0.08"),
                LoyaltyStatus.GOLD: Decimal("0.10"),
                LoyaltyStatus.PLATINUM: Decimal("0.12"),
                LoyaltyStatus.DIAMOND: Decimal("0.15"),
            }
        )
        pricing_service = PricingService(
            loyalty_policy=loyalty_policy,
            group_rules=self._rules_repo.get_group_rules(),
            child_policy_by_group=self._rules_repo.get_child_policies(),
        )
        selector = DatePriceSelector(pricing_service)
        use_case = CalculateMatchesForAllGuests(
            rates_repo=self._rates_repo,
            offers_repo=self._offers_repo,
            guests_repo=self._guests_repo,
            rules_repo=self._rules_repo,
            pricing_service=pricing_service,
            period_builder=PeriodBuilder,
            selector=selector,
        )

        def _do_recalculation() -> str:
            results = use_case.execute(
                date_from=actual_date_from,
                date_to=actual_date_to,
                booking_date=actual_booking_date,
            )

            run_id = datetime.now().strftime("%Y%m%d_%H%M") + "_" + uuid4().hex[:6]
            computed_at = datetime.now()
            all_records: list[MatchedDateRecord] = []
            desired_records: list[MatchedDateRecord] = []
            for result in results:
                for line in result.matched_lines:
                    rec = MatchedDateRecord(
                        guest_id=result.guest_id,
                        date=line.date,
                        category_name=line.category_name,
                        group_id=line.group_id,
                        tariff=line.tariff_code,
                        old_price_minor=line.old_price.amount_minor,
                        new_price_minor=line.new_price.amount_minor,
                        offer_id=line.offer_id,
                        offer_title=line.offer_title,
                        offer_repr=line.offer_repr,
                        offer_min_nights=line.offer_min_nights,
                        loyalty_status=line.applied_loyalty_status,
                        loyalty_percent=_parse_percent(line.applied_loyalty_percent),
                        bank_status=line.applied_bank_status.value if line.applied_bank_status else None,
                        bank_percent=line.applied_bank_percent,
                        availability_start=line.availability_period.start,
                        availability_end=line.availability_period.end,
                        computed_at=computed_at,
                        period_end=line.date,
                    )
                    all_records.append(rec)
                    if line.new_price <= result.desired_price_per_night:
                        desired_records.append(rec)

            self._matches_run_repo.replace_run(run_id, all_records)
            self._desired_matches_run_repo.replace_run(run_id, desired_records)
            return run_id

        coordinator = TelegramUseCasesAdapter._recalculation_coordinator
        if coordinator is None:
            logger.warning("recalculate_coordinator_missing trigger=%s", trigger)
            return _do_recalculation()
        result = coordinator.run(trigger=trigger, runner=_do_recalculation)
        return result.run_id

    def get_best_periods(self, *, guest_id: str, group_id: str, top_k: int = 3) -> list[PeriodPickDTO]:
        today = date.today()
        query = GetBestPeriodQuery(
            guest_id=guest_id,
            group_id=group_id.strip().upper(),
            date_from=today,
            date_to=today + timedelta(days=90),
            booking_date=today,
            top_k=top_k,
        )
        _, picks = self._best_periods_uc.execute(query)
        return picks

    def get_best_period_categories(self, *, guest_id: str, group_id: str, top_k: int = 200) -> list[str]:
        picks = self.get_best_periods(guest_id=guest_id, group_id=group_id, top_k=top_k)
        return sorted({pick.category_name for pick in picks})

    def get_group_categories_for_guest(self, *, guest_id: str, group_id: str) -> list[str]:
        guest = self.get_guest_profile(guest_id=guest_id)
        if guest is None:
            return []

        today = date.today()
        rates = self._rates_repo.get_daily_rates(today, today + timedelta(days=90))
        group_rules = self._rules_repo.get_group_rules()
        return find_group_categories_for_guest(
            daily_rates=rates,
            group_rules=group_rules,
            guest=guest,
            group_id=group_id,
        )

    def get_best_period_details_for_category(
        self,
        *,
        guest_id: str,
        group_id: str,
        category_name: str,
    ) -> tuple[PeriodPickDTO | None, list[PeriodQuote]]:
        guest = self.get_guest_profile(guest_id=guest_id)
        if guest is None:
            return None, []

        today = date.today()
        date_to = today + timedelta(days=90)
        rates = self._rates_repo.get_daily_rates(today, date_to)
        offers = self._offers_repo.get_offers(today)
        group_rules = self._rules_repo.get_group_rules()
        child_policies = self._rules_repo.get_child_policies()
        ctx = PricingContext(
            booking_date=today,
            loyalty_status=guest.loyalty_status,
            bank_status=guest.bank_status,
            children_4_13=guest.occupancy.children_4_13,
        )
        selected_pick = find_best_period_for_category(
            daily_rates=rates,
            offers=offers,
            group_rules=group_rules,
            child_policies=child_policies,
            guest=guest,
            ctx=ctx,
            group_id=group_id,
            category_name=category_name,
            date_from=today,
            date_to=date_to,
        )
        if selected_pick is None:
            return None, []

        _, quotes = self.get_period_quotes(
            guest_id=guest_id,
            period_start=selected_pick.start_date,
            period_end=selected_pick.end_date_inclusive,
            group_ids={group_id.strip().upper()},
        )
        filtered_quotes = [quote for quote in quotes if quote.category_name == category_name]
        return selected_pick, filtered_quotes

    def get_period_quotes(
        self,
        *,
        guest_id: str,
        period_start: date,
        period_end: date,
        group_ids: set[str] | None,
    ) -> tuple[str, list[PeriodQuote]]:
        query = GetPeriodQuotesQuery(
            guest_id=guest_id,
            period_start=period_start,
            period_end=period_end,
            group_ids=group_ids,
            run_id=None,
        )
        return self._period_quotes_uc.execute(query)

    def get_guest_profile(self, *, guest_id: str) -> GuestPreferences | None:
        guests = self._guests_repo.get_active_guests()
        return next((g for g in guests if g.guest_id == guest_id), None)

    def update_guest_profile(
        self,
        *,
        guest_id: str,
        adults: int | None = None,
        children_4_13: int | None = None,
        infants_0_3: int | None = None,
        allowed_groups: set[str] | None = None,
        loyalty_status: str | None = None,
        bank_status: str | None = None,
        desired_price_rub: Decimal | None = None,
    ) -> None:
        current = self.get_guest_profile(guest_id=guest_id)
        if current is None:
            raise ValueError(f"Guest not found: {guest_id}")

        loyalty_obj = current.loyalty_status
        bank_obj = current.bank_status
        if loyalty_status is not None:
            loyalty_obj = LoyaltyStatus(loyalty_status.lower())
        if bank_status is not None:
            bank_obj = BankStatus(bank_status) if bank_status else None
        if bank_obj is not None:
            loyalty_obj = None

        desired_minor = (
            int((desired_price_rub * Decimal("100")).to_integral_value())
            if desired_price_rub is not None
            else current.desired_price_per_night.amount_minor
        )
        updated = GuestPreferences(
            desired_price_per_night=Money.from_minor(desired_minor, currency=current.desired_price_per_night.currency),
            loyalty_status=loyalty_obj,
            bank_status=bank_obj,
            allowed_groups=(allowed_groups if allowed_groups is not None else current.effective_allowed_groups),
            occupancy=Occupancy(
                adults=adults if adults is not None else current.occupancy.adults,
                children_4_13=children_4_13 if children_4_13 is not None else current.occupancy.children_4_13,
                infants=infants_0_3 if infants_0_3 is not None else current.occupancy.infants,
            ),
            guest_id=guest_id,
            guest_name=current.guest_name,
            guest_phone=current.guest_phone,
        )
        self._guests_repo.create_guest(updated)
        self.recalculate_matches(trigger=f"profile_update:{guest_id}")

    def get_available_categories(self, *, guest_id: str) -> list[str]:
        run_id = self._desired_matches_run_repo.get_latest_run_id()
        if not run_id:
            return []
        rows = self._desired_matches_run_repo.get_run_rows(run_id)
        names = sorted({r.category_name for r in rows if r.guest_id == guest_id})
        return names

    def get_available_categories_with_groups(self, *, guest_id: str) -> list[tuple[str, str]]:
        run_id = self._desired_matches_run_repo.get_latest_run_id()
        if not run_id:
            return []
        rows = self._desired_matches_run_repo.get_run_rows(run_id)
        pairs = sorted(
            {
                (r.category_name, r.group_id)
                for r in rows
                if r.guest_id == guest_id and r.category_name and r.group_id
            },
            key=lambda x: (x[1], x[0]),
        )
        return pairs

    def get_category_matches(self, *, guest_id: str, category_name: str) -> tuple[str, list[MatchedDateRecord]]:
        run_id = self._desired_matches_run_repo.get_latest_run_id()
        if not run_id:
            return "", []
        rows = self._desired_matches_run_repo.get_run_rows(run_id)
        out = [
            r
            for r in rows
            if r.guest_id == guest_id and r.category_name == category_name
        ]
        out.sort(key=lambda x: (x.date, x.tariff))
        return run_id, out

    def list_telegram_user_ids_for_guest(self, *, guest_id: str) -> list[int]:
        raw_ids = self._identities_repo.list_external_user_ids(provider=self._provider(), guest_id=guest_id)
        out: list[int] = []
        for raw in raw_ids:
            try:
                out.append(int(raw))
            except ValueError:
                continue
        return out

    def get_offer_text(self, *, offer_id: str | None, offer_title: str | None) -> str | None:
        if not offer_id and not offer_title:
            return None
        offers = self._offers_repo.get_offers(date.today())
        for offer in offers:
            if offer_id and offer.id == offer_id:
                return offer.description
        for offer in offers:
            if offer_title and offer.title == offer_title:
                return offer.description
        return None

    def build_notification_targets(self) -> list[GuestNotificationTarget]:
        guests = {x.guest_id: x for x in self._guests_repo.get_active_guests() if x.guest_id}
        out: list[GuestNotificationTarget] = []
        for guest_id in sorted(guests.keys()):
            categories = self.get_available_categories(guest_id=guest_id)
            telegram_ids = self.list_telegram_user_ids_for_guest(guest_id=guest_id)
            if not telegram_ids:
                continue
            guest = guests[guest_id]
            out.append(
                GuestNotificationTarget(
                    guest_id=guest_id,
                    guest_name=guest.guest_name or "Гость",
                    telegram_user_ids=telegram_ids,
                    category_names=categories,
                )
            )
        return out

    def get_last_room_dates(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariffs: set[str] | None = None,
    ) -> list[date]:
        profile = self.get_guest_profile(guest_id=guest_id)
        if profile is None:
            return []
        adults = profile.occupancy.adults
        tariffs_norm = {x.strip().lower() for x in tariffs} if tariffs else None
        rates = self._rates_repo.get_daily_rates(period_start, period_end)
        out = sorted(
            {
                r.date
                for r in rates
                if r.category_id == category_name
                and r.adults_count == adults
                and r.is_last_room
                and r.is_available
                and (tariffs_norm is None or r.tariff_code.strip().lower() in tariffs_norm)
                and period_start <= r.date <= period_end
            }
        )
        return out


def _parse_percent(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = value.strip().replace("%", "")
    if not cleaned:
        return None
    return (Decimal(cleaned) / Decimal("100")).quantize(Decimal("0.0001"))
