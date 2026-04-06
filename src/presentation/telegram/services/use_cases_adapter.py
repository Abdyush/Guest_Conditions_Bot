from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from src.application.dto.admin_dashboard import AdminReport, AdminStatistics
from src.application.dto.travelline_publish_report import TravellinePublishRunReport
from src.application.dto.get_best_period_query import GetBestPeriodQuery
from src.application.dto.get_period_quotes_query import GetPeriodQuotesQuery
from src.application.dto.guest_notification_batch import GuestNotificationBatch
from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.dto.period_pick import PeriodPickDTO
from src.application.dto.period_quote import PeriodQuote
from src.application.use_cases.calculate_matches_for_all_guests import CalculateMatchesForAllGuests
from src.application.use_cases.find_best_period_for_category import find_best_period_for_category
from src.application.use_cases.find_best_periods_in_group import DEFAULT_LOYALTY_POLICY
from src.application.use_cases.find_group_categories_for_guest import find_group_categories_for_guest
from src.application.use_cases.get_admin_reports import GetAdminReports
from src.application.use_cases.get_admin_statistics import GetAdminStatistics
from src.application.use_cases.get_latest_travelline_publish_report import GetLatestTravellinePublishReport
from src.application.use_cases.get_best_periods_for_guest_in_group import GetBestPeriodsForGuestInGroup
from src.application.use_cases.get_period_quotes_from_matches_run import GetPeriodQuotesFromMatchesRun
from src.application.use_cases.prepare_guest_notification_batches import PrepareGuestNotificationBatches
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.category_capacity import Occupancy, can_fit
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext, PricingService
from src.domain.value_objects.bank import BankStatus
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.domain.value_objects.money import Money
from src.infrastructure.repositories.postgres_admin_events_repository import PostgresAdminEventsRepository
from src.infrastructure.repositories.postgres_admin_insights_repository import PostgresAdminInsightsRepository
from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_desired_matches_run_repository import PostgresDesiredMatchesRunRepository
from src.infrastructure.repositories.postgres_guests_repository import PostgresGuestsRepository
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository
from src.infrastructure.repositories.postgres_notifications_repository import PostgresNotificationsRepository
from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
from src.infrastructure.repositories.postgres_travelline_publish_report_repository import PostgresTravellinePublishReportRepository
from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository
from src.infrastructure.synchronization.recalculation_run_coordinator import RecalculationRunCoordinator


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TelegramUseCasesDependencies:
    identities_repo: PostgresUserIdentitiesRepository
    guests_repo: PostgresGuestsRepository
    admin_events_repo: PostgresAdminEventsRepository
    admin_insights_repo: PostgresAdminInsightsRepository
    rates_repo: PostgresDailyRatesRepository
    offers_repo: PostgresOffersRepository
    rules_repo: PostgresRulesRepository
    travelline_publish_report_repo: PostgresTravellinePublishReportRepository
    matches_run_repo: PostgresMatchesRunRepository
    desired_matches_run_repo: PostgresDesiredMatchesRunRepository
    notifications_repo: PostgresNotificationsRepository
    proactive_notification_cooldown_days: int = 7
    matches_lookahead_days: int = 90
    recalculation_coordinator: RecalculationRunCoordinator | None = None


@dataclass(frozen=True, slots=True)
class TelegramServicesContext:
    identities_repo: PostgresUserIdentitiesRepository
    guests_repo: PostgresGuestsRepository
    admin_events_repo: PostgresAdminEventsRepository
    admin_insights_repo: PostgresAdminInsightsRepository
    rates_repo: PostgresDailyRatesRepository
    offers_repo: PostgresOffersRepository
    rules_repo: PostgresRulesRepository
    travelline_publish_report_repo: PostgresTravellinePublishReportRepository
    matches_run_repo: PostgresMatchesRunRepository
    desired_matches_run_repo: PostgresDesiredMatchesRunRepository
    notifications_repo: PostgresNotificationsRepository
    best_periods_uc: GetBestPeriodsForGuestInGroup
    period_quotes_uc: GetPeriodQuotesFromMatchesRun
    get_admin_reports_uc: GetAdminReports
    get_admin_statistics_uc: GetAdminStatistics
    get_latest_travelline_publish_report_uc: GetLatestTravellinePublishReport
    prepare_notification_batches_uc: PrepareGuestNotificationBatches
    matches_lookahead_days: int
    recalculation_coordinator: RecalculationRunCoordinator | None
    provider: str = "telegram"


@dataclass(frozen=True, slots=True)
class TelegramPresentationServices:
    identity: TelegramIdentityFacade
    profile: TelegramProfileFacade
    available_offers: TelegramAvailableOffersFacade
    best_periods: TelegramBestPeriodsFacade
    period_quotes: TelegramPeriodQuotesFacade
    notifications: TelegramNotificationsFacade
    admin: TelegramAdminFacade
    system: TelegramSystemFacade


class TelegramBaseFacade:
    def __init__(self, *, ctx: TelegramServicesContext):
        self._ctx = ctx

    def _get_guest_profile(self, *, guest_id: str) -> GuestPreferences | None:
        guests = self._ctx.guests_repo.get_active_guests()
        return next((guest for guest in guests if guest.guest_id == guest_id), None)

    def _get_offer_text(self, *, offer_id: str | None, offer_title: str | None) -> str | None:
        if not offer_id and not offer_title:
            return None
        offers = self._ctx.offers_repo.get_offers(date.today())
        for offer in offers:
            if offer_id and offer.id == offer_id:
                return offer.description
        for offer in offers:
            if offer_title and offer.title == offer_title:
                return offer.description
        return None

    def _get_last_room_dates(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariffs: set[str] | None = None,
    ) -> list[date]:
        profile = self._get_guest_profile(guest_id=guest_id)
        if profile is None:
            return []
        adults = profile.occupancy.adults
        tariffs_norm = {value.strip().lower() for value in tariffs} if tariffs else None
        rates = self._ctx.rates_repo.get_daily_rates(period_start, period_end)
        return sorted(
            {
                rate.date
                for rate in rates
                if rate.category_id == category_name
                and rate.adults_count == adults
                and rate.is_last_room
                and rate.is_available
                and (tariffs_norm is None or rate.tariff_code.strip().lower() in tariffs_norm)
                and period_start <= rate.date <= period_end
            }
        )

    def _recalculate_matches(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        booking_date: date | None = None,
        trigger: str = "direct",
    ) -> str:
        today = date.today()
        actual_date_from = date_from or today
        actual_date_to = date_to or (today + timedelta(days=self._ctx.matches_lookahead_days))
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
            group_rules=self._ctx.rules_repo.get_group_rules(),
            child_policy_by_group=self._ctx.rules_repo.get_child_policies(),
        )
        selector = DatePriceSelector(pricing_service)
        use_case = CalculateMatchesForAllGuests(
            rates_repo=self._ctx.rates_repo,
            offers_repo=self._ctx.offers_repo,
            guests_repo=self._ctx.guests_repo,
            rules_repo=self._ctx.rules_repo,
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
                    record = MatchedDateRecord(
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
                    all_records.append(record)
                    if line.new_price <= result.desired_price_per_night:
                        desired_records.append(record)

            self._ctx.matches_run_repo.replace_run(run_id, all_records)
            self._ctx.desired_matches_run_repo.replace_run(run_id, desired_records)
            return run_id

        coordinator = self._ctx.recalculation_coordinator
        if coordinator is None:
            logger.warning("recalculate_coordinator_missing trigger=%s", trigger)
            return _do_recalculation()
        result = coordinator.run(trigger=trigger, runner=_do_recalculation)
        return result.run_id


class TelegramIdentityFacade(TelegramBaseFacade):
    def resolve_guest_id(self, *, telegram_user_id: int) -> str | None:
        return self._ctx.identities_repo.resolve_guest_id(
            provider=self._ctx.provider,
            external_user_id=str(telegram_user_id),
        )

    def unbind_telegram(self, *, telegram_user_id: int) -> None:
        self._ctx.identities_repo.delete_identity(
            provider=self._ctx.provider,
            external_user_id=str(telegram_user_id),
        )

    def bind_guest_id(self, *, telegram_user_id: int, guest_id: str) -> bool:
        normalized_guest_id = guest_id.strip()
        if not normalized_guest_id:
            return False
        guests = self._ctx.guests_repo.get_active_guests()
        if not any(guest.guest_id == normalized_guest_id for guest in guests):
            return False

        self._ctx.identities_repo.upsert_identity(
            provider=self._ctx.provider,
            external_user_id=str(telegram_user_id),
            guest_id=normalized_guest_id,
        )
        return True

    def bind_by_phone(self, *, telegram_user_id: int, phone: str) -> str | None:
        guest_id = self._ctx.identities_repo.resolve_guest_id(
            provider="phone",
            external_user_id=phone,
        )
        if not guest_id:
            return None
        guests = self._ctx.guests_repo.get_active_guests()
        if not any(guest.guest_id == guest_id for guest in guests):
            self._ctx.identities_repo.delete_identity(provider="phone", external_user_id=phone)
            return None
        self._ctx.identities_repo.upsert_identity(
            provider=self._ctx.provider,
            external_user_id=str(telegram_user_id),
            guest_id=guest_id,
        )
        return guest_id

    def list_telegram_user_ids_for_guest(self, *, guest_id: str) -> list[int]:
        raw_ids = self._ctx.identities_repo.list_external_user_ids(provider=self._ctx.provider, guest_id=guest_id)
        out: list[int] = []
        for raw in raw_ids:
            try:
                out.append(int(raw))
            except ValueError:
                continue
        return out


class TelegramProfileFacade(TelegramBaseFacade):
    def get_guest_profile(self, *, guest_id: str) -> GuestPreferences | None:
        return self._get_guest_profile(guest_id=guest_id)

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
            allowed_groups={value.strip().upper() for value in allowed_groups if value.strip()},
            occupancy=Occupancy(adults=adults, children_4_13=children_4_13, infants=infants_0_3),
            guest_name=name.strip(),
            guest_phone=phone,
        )
        guest_id = self._ctx.guests_repo.create_guest(guest)
        self._ctx.identities_repo.upsert_identity(provider="phone", external_user_id=phone, guest_id=guest_id)
        self._ctx.identities_repo.upsert_identity(
            provider=self._ctx.provider,
            external_user_id=str(telegram_user_id),
            guest_id=guest_id,
        )
        self._recalculate_matches(trigger=f"registration:{telegram_user_id}")
        return guest_id

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
        current = self._get_guest_profile(guest_id=guest_id)
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
        self._ctx.guests_repo.create_guest(updated)
        self._recalculate_matches(trigger=f"profile_update:{guest_id}")


class TelegramAvailableOffersFacade(TelegramBaseFacade):
    def get_available_categories(self, *, guest_id: str) -> list[str]:
        run_id = self._ctx.desired_matches_run_repo.get_latest_run_id()
        if not run_id:
            return []
        rows = self._ctx.desired_matches_run_repo.get_run_rows(run_id)
        return sorted({row.category_name for row in rows if row.guest_id == guest_id})

    def get_available_categories_with_groups(self, *, guest_id: str) -> list[tuple[str, str]]:
        run_id = self._ctx.desired_matches_run_repo.get_latest_run_id()
        if not run_id:
            return []
        rows = self._ctx.desired_matches_run_repo.get_run_rows(run_id)
        return sorted(
            {
                (row.category_name, row.group_id)
                for row in rows
                if row.guest_id == guest_id and row.category_name and row.group_id
            },
            key=lambda item: (item[1], item[0]),
        )

    def get_category_matches(self, *, guest_id: str, category_name: str) -> tuple[str, list[MatchedDateRecord]]:
        run_id = self._ctx.desired_matches_run_repo.get_latest_run_id()
        if not run_id:
            return "", []
        rows = self._ctx.desired_matches_run_repo.get_run_rows(run_id)
        out = [row for row in rows if row.guest_id == guest_id and row.category_name == category_name]
        out.sort(key=lambda item: (item.date, item.tariff))
        return run_id, out

    def get_last_room_dates(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariffs: set[str] | None = None,
    ) -> list[date]:
        return self._get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period_start,
            period_end=period_end,
            tariffs=tariffs,
        )

    def get_offer_text(self, *, offer_id: str | None, offer_title: str | None) -> str | None:
        return self._get_offer_text(offer_id=offer_id, offer_title=offer_title)


class TelegramBestPeriodsFacade(TelegramBaseFacade):
    def get_group_categories_for_guest(self, *, guest_id: str, group_id: str) -> list[str]:
        guest = self._get_guest_profile(guest_id=guest_id)
        if guest is None:
            return []

        today = date.today()
        rates = self._ctx.rates_repo.get_daily_rates(today, today + timedelta(days=self._ctx.matches_lookahead_days))
        group_rules = self._ctx.rules_repo.get_group_rules()
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
        guest = self._get_guest_profile(guest_id=guest_id)
        if guest is None:
            return None, []

        today = date.today()
        date_to = today + timedelta(days=self._ctx.matches_lookahead_days)
        rates = self._ctx.rates_repo.get_daily_rates(today, date_to)
        offers = self._ctx.offers_repo.get_offers(today)
        group_rules = self._ctx.rules_repo.get_group_rules()
        child_policies = self._ctx.rules_repo.get_child_policies()
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

        quotes = _build_period_quotes_from_live_rates(
            guest=guest,
            rates=rates,
            offers=offers,
            group_rules=group_rules,
            child_policies=child_policies,
            query=GetPeriodQuotesQuery(
                guest_id=guest_id,
                period_start=selected_pick.start_date,
                period_end=selected_pick.end_date_inclusive,
                group_ids={group_id.strip().upper()},
            ),
            booking_date=today,
        )
        filtered_quotes = [quote for quote in quotes if quote.category_name == category_name]
        return selected_pick, filtered_quotes

    def get_last_room_dates(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariffs: set[str] | None = None,
    ) -> list[date]:
        return self._get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period_start,
            period_end=period_end,
            tariffs=tariffs,
        )

    def get_available_dates_for_category(
        self,
        *,
        guest_id: str,
        group_id: str,
        category_name: str,
    ) -> list[date]:
        guest = self._get_guest_profile(guest_id=guest_id)
        if guest is None:
            return []

        today = date.today()
        date_to = today + timedelta(days=self._ctx.matches_lookahead_days)
        normalized_group_id = group_id.strip().upper()
        normalized_category_name = category_name.strip()
        allowed_groups = guest.effective_allowed_groups
        group_rules = self._ctx.rules_repo.get_group_rules()

        out = {
            rate.date
            for rate in self._ctx.rates_repo.get_daily_rates(today, date_to)
            if rate.group_id.strip().upper() == normalized_group_id
            and rate.category_id == normalized_category_name
            and rate.adults_count == guest.occupancy.adults
            and rate.is_available
            and (allowed_groups is None or rate.group_id in allowed_groups)
            and ((rule := group_rules.get(rate.group_id)) is None or can_fit(rule, guest.occupancy))
        }
        return sorted(out)

    def get_offer_text(self, *, offer_id: str | None, offer_title: str | None) -> str | None:
        return self._get_offer_text(offer_id=offer_id, offer_title=offer_title)


class TelegramPeriodQuotesFacade(TelegramBaseFacade):
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
        return self._ctx.period_quotes_uc.execute(query)

    def get_last_room_dates(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariffs: set[str] | None = None,
    ) -> list[date]:
        return self._get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period_start,
            period_end=period_end,
            tariffs=tariffs,
        )

    def get_offer_text(self, *, offer_id: str | None, offer_title: str | None) -> str | None:
        return self._get_offer_text(offer_id=offer_id, offer_title=offer_title)


class TelegramNotificationsFacade(TelegramBaseFacade):
    def prepare_new_notification_batches(self, *, run_id: str, as_of_date: date | None = None) -> list[GuestNotificationBatch]:
        actual_date = as_of_date or date.today()
        return self._ctx.prepare_notification_batches_uc.execute(run_id=run_id, as_of_date=actual_date)

    def mark_notification_rows_sent(self, *, run_id: str, rows: list[MatchedDateRecord]) -> None:
        self._ctx.notifications_repo.mark_sent(rows, run_id=run_id)

    def get_notification_categories_with_groups(self, *, guest_id: str, run_id: str) -> list[tuple[str, str]]:
        rows = self._ctx.notifications_repo.get_run_rows(run_id, guest_id=guest_id)
        return sorted(
            {
                (row.category_name, row.group_id)
                for row in rows
                if row.guest_id == guest_id and row.category_name and row.group_id
            },
            key=lambda item: (item[1], item[0]),
        )

    def get_notification_category_matches(self, *, guest_id: str, run_id: str, category_name: str) -> tuple[str, list[MatchedDateRecord]]:
        rows = self._ctx.notifications_repo.get_run_rows(run_id, guest_id=guest_id)
        out = [
            row
            for row in rows
            if row.guest_id == guest_id and row.category_name == category_name
        ]
        out.sort(key=lambda item: (item.date, item.period_end or item.date, item.tariff))
        return run_id, out

    def get_last_room_dates(
        self,
        *,
        guest_id: str,
        category_name: str,
        period_start: date,
        period_end: date,
        tariffs: set[str] | None = None,
    ) -> list[date]:
        return self._get_last_room_dates(
            guest_id=guest_id,
            category_name=category_name,
            period_start=period_start,
            period_end=period_end,
            tariffs=tariffs,
        )

    def get_offer_text(self, *, offer_id: str | None, offer_title: str | None) -> str | None:
        return self._get_offer_text(offer_id=offer_id, offer_title=offer_title)


class TelegramAdminFacade(TelegramBaseFacade):
    def log_admin_event(
        self,
        *,
        event_type: str,
        status: str,
        trigger: str | None = None,
        message: str | None = None,
        user_id: int | None = None,
    ) -> None:
        self._ctx.admin_events_repo.log_event(
            event_type=event_type,
            status=status,
            trigger=trigger,
            message=message,
            user_id=user_id,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    def get_admin_reports(self) -> dict[str, AdminReport]:
        return self._ctx.get_admin_reports_uc.execute(now=datetime.now(timezone.utc).replace(tzinfo=None))

    def get_admin_statistics(self) -> AdminStatistics:
        return self._ctx.get_admin_statistics_uc.execute(now=datetime.now(timezone.utc).replace(tzinfo=None))

    def get_latest_travelline_publish_report(self) -> TravellinePublishRunReport | None:
        return self._ctx.get_latest_travelline_publish_report_uc.execute()


class TelegramSystemFacade(TelegramBaseFacade):
    def recalculate_matches(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        booking_date: date | None = None,
        trigger: str = "direct",
    ) -> str:
        return self._recalculate_matches(
            date_from=date_from,
            date_to=date_to,
            booking_date=booking_date,
            trigger=trigger,
        )


def build_telegram_presentation_services(*, deps: TelegramUseCasesDependencies) -> TelegramPresentationServices:
    ctx = TelegramServicesContext(
        identities_repo=deps.identities_repo,
        guests_repo=deps.guests_repo,
        admin_events_repo=deps.admin_events_repo,
        admin_insights_repo=deps.admin_insights_repo,
        rates_repo=deps.rates_repo,
        offers_repo=deps.offers_repo,
        rules_repo=deps.rules_repo,
        travelline_publish_report_repo=deps.travelline_publish_report_repo,
        matches_run_repo=deps.matches_run_repo,
        desired_matches_run_repo=deps.desired_matches_run_repo,
        notifications_repo=deps.notifications_repo,
        best_periods_uc=GetBestPeriodsForGuestInGroup(
            rates_repo=deps.rates_repo,
            offers_repo=deps.offers_repo,
            guests_repo=deps.guests_repo,
            rules_repo=deps.rules_repo,
        ),
        period_quotes_uc=GetPeriodQuotesFromMatchesRun(deps.matches_run_repo),
        get_admin_reports_uc=GetAdminReports(events_repo=deps.admin_events_repo),
        get_admin_statistics_uc=GetAdminStatistics(
            insights_repo=deps.admin_insights_repo,
            events_repo=deps.admin_events_repo,
        ),
        get_latest_travelline_publish_report_uc=GetLatestTravellinePublishReport(
            repo=deps.travelline_publish_report_repo,
        ),
        prepare_notification_batches_uc=PrepareGuestNotificationBatches(
            desired_matches_repo=deps.desired_matches_run_repo,
            notifications_repo=deps.notifications_repo,
            guests_repo=deps.guests_repo,
            identities_repo=deps.identities_repo,
            provider="telegram",
            reminder_cooldown_days=deps.proactive_notification_cooldown_days,
        ),
        matches_lookahead_days=deps.matches_lookahead_days,
        recalculation_coordinator=deps.recalculation_coordinator,
    )
    return TelegramPresentationServices(
        identity=TelegramIdentityFacade(ctx=ctx),
        profile=TelegramProfileFacade(ctx=ctx),
        available_offers=TelegramAvailableOffersFacade(ctx=ctx),
        best_periods=TelegramBestPeriodsFacade(ctx=ctx),
        period_quotes=TelegramPeriodQuotesFacade(ctx=ctx),
        notifications=TelegramNotificationsFacade(ctx=ctx),
        admin=TelegramAdminFacade(ctx=ctx),
        system=TelegramSystemFacade(ctx=ctx),
    )


def _parse_percent(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = value.strip().replace("%", "")
    if not cleaned:
        return None
    return (Decimal(cleaned) / Decimal("100")).quantize(Decimal("0.0001"))


def _build_period_quotes_from_live_rates(
    *,
    guest: GuestPreferences,
    rates,
    offers,
    group_rules,
    child_policies,
    query: GetPeriodQuotesQuery,
    booking_date: date,
) -> list[PeriodQuote]:
    normalized_group_ids = (
        {group_id.strip().upper() for group_id in query.group_ids}
        if query.group_ids is not None
        else None
    )
    allowed_groups = guest.effective_allowed_groups

    filtered_rates = [
        rate
        for rate in rates
        if query.period_start <= rate.date <= query.period_end
        and rate.adults_count == guest.occupancy.adults
        and rate.is_available
        and (normalized_group_ids is None or rate.group_id.strip().upper() in normalized_group_ids)
        and (allowed_groups is None or rate.group_id in allowed_groups)
        and ((rule := group_rules.get(rate.group_id)) is None or can_fit(rule, guest.occupancy))
    ]
    if not filtered_rates:
        return []

    selector = DatePriceSelector(
        pricing=PricingService(
            loyalty_policy=DEFAULT_LOYALTY_POLICY,
            group_rules=group_rules,
            child_policy_by_group=child_policies,
        )
    )
    ctx = PricingContext(
        booking_date=booking_date,
        loyalty_status=guest.loyalty_status,
        bank_status=guest.bank_status,
        children_4_13=guest.occupancy.children_4_13,
    )
    periods = PeriodBuilder.build(filtered_rates)
    best_map = selector.best_prices_by_date(
        daily_rates=filtered_rates,
        periods=periods,
        offers=offers,
        ctx=ctx,
    )

    candidates = [
        line
        for line in best_map.values()
        if query.period_start <= line.day <= query.period_end
        and (normalized_group_ids is None or line.group_id.strip().upper() in normalized_group_ids)
    ]
    if not candidates:
        return []

    days_in_period = (query.period_end - query.period_start).days + 1
    coverage: dict[tuple[str, str, str], set[date]] = defaultdict(set)
    for line in candidates:
        coverage[(line.category_id, line.group_id, line.tariff_code)].add(line.day)

    valid_tariffs = {
        key
        for key, covered_days in coverage.items()
        if len(covered_days) == days_in_period
    }
    if not valid_tariffs:
        return []

    grouped_lines: dict[tuple[str, str, str], list] = defaultdict(list)
    for line in candidates:
        key = (line.category_id, line.group_id, line.tariff_code)
        if key in valid_tariffs:
            grouped_lines[key].append(line)

    quotes: list[PeriodQuote] = []
    for (category_name, group_id, tariff), tariff_lines in grouped_lines.items():
        ordered_lines = sorted(tariff_lines, key=lambda item: item.day)
        segment_start = ordered_lines[0].day
        segment_end = ordered_lines[0].day
        total_old_minor = ordered_lines[0].old_price.amount_minor
        total_new_minor = ordered_lines[0].new_price.amount_minor
        segment_nights = 1
        current_signature = _candidate_quote_signature(ordered_lines[0])

        for line in ordered_lines[1:]:
            line_signature = _candidate_quote_signature(line)
            if line.day == segment_end + timedelta(days=1) and line_signature == current_signature:
                segment_end = line.day
                total_old_minor += line.old_price.amount_minor
                total_new_minor += line.new_price.amount_minor
                segment_nights += 1
                continue

            quotes.append(
                _to_period_quote(
                    category_name=category_name,
                    group_id=group_id,
                    tariff=tariff,
                    query=query,
                    segment_start=segment_start,
                    segment_end=segment_end,
                    total_old_minor=total_old_minor,
                    total_new_minor=total_new_minor,
                    nights=segment_nights,
                    signature=current_signature,
                )
            )
            segment_start = line.day
            segment_end = line.day
            total_old_minor = line.old_price.amount_minor
            total_new_minor = line.new_price.amount_minor
            segment_nights = 1
            current_signature = line_signature

        quotes.append(
            _to_period_quote(
                category_name=category_name,
                group_id=group_id,
                tariff=tariff,
                query=query,
                segment_start=segment_start,
                segment_end=segment_end,
                total_old_minor=total_old_minor,
                total_new_minor=total_new_minor,
                nights=segment_nights,
                signature=current_signature,
            )
        )

    quotes.sort(key=lambda item: (item.group_id, item.category_name, item.tariff, item.applied_from))
    return quotes


def _candidate_quote_signature(line) -> tuple:
    return (
        line.offer_id,
        line.offer_title,
        line.offer_repr,
        line.loyalty_status,
        line.loyalty_percent,
        line.applied_bank_status.value if line.applied_bank_status is not None else None,
        str(line.applied_bank_percent) if line.applied_bank_percent is not None else None,
    )


def _to_period_quote(
    *,
    category_name: str,
    group_id: str,
    tariff: str,
    query: GetPeriodQuotesQuery,
    segment_start: date,
    segment_end: date,
    total_old_minor: int,
    total_new_minor: int,
    nights: int,
    signature: tuple,
) -> PeriodQuote:
    (
        offer_id,
        offer_title,
        offer_repr,
        loyalty_status,
        loyalty_percent,
        bank_status,
        bank_percent,
    ) = signature
    return PeriodQuote(
        category_name=category_name,
        group_id=group_id,
        tariff=tariff,
        from_date=query.period_start,
        to_date=query.period_end,
        applied_from=segment_start,
        applied_to=segment_end,
        nights=nights,
        total_old_minor=total_old_minor,
        total_new_minor=total_new_minor,
        offer_id=offer_id,
        offer_title=offer_title,
        offer_repr=offer_repr,
        loyalty_status=loyalty_status,
        loyalty_percent=loyalty_percent,
        bank_status=bank_status,
        bank_percent=bank_percent,
    )
