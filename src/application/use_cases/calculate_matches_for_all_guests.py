from __future__ import annotations

from datetime import date

from src.application.dto.date_line import DateLineDTO
from src.application.dto.guest_result import GuestResult
from src.application.dto.period_pick import PeriodPickDTO
from src.application.ports.guests_repository import GuestsRepository
from src.application.ports.offers_repository import OffersRepository
from src.application.ports.rates_repository import RatesRepository
from src.application.ports.rules_repository import RulesRepository
from src.application.use_cases.find_best_periods_in_group import find_best_periods_in_group
from src.domain.entities.guest_preferences import GuestPreferences
from src.domain.services.category_capacity import can_fit
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingContext, PricingService


class CalculateMatchesForAllGuests:
    def __init__(
        self,
        *,
        rates_repo: RatesRepository,
        offers_repo: OffersRepository,
        guests_repo: GuestsRepository,
        rules_repo: RulesRepository,
        pricing_service: PricingService,
        period_builder: PeriodBuilder,
        selector: DatePriceSelector,
    ):
        self._rates_repo = rates_repo
        self._offers_repo = offers_repo
        self._guests_repo = guests_repo
        self._rules_repo = rules_repo
        self._pricing_service = pricing_service
        self._period_builder = period_builder
        self._selector = selector

    def execute(self, *, date_from: date, date_to: date, booking_date: date) -> list[GuestResult]:
        rates = self._rates_repo.get_daily_rates(date_from, date_to)
        offers = self._offers_repo.get_offers(booking_date)
        group_rules = self._rules_repo.get_group_rules()
        child_policies = self._rules_repo.get_child_policies()
        _ = self._rules_repo.get_category_to_group()
        guests = self._guests_repo.get_active_guests()

        results: list[GuestResult] = []
        for idx, guest in enumerate(guests, start=1):
            guest_rates = self._filter_rates_for_guest(rates, guest=guest, group_rules=group_rules)
            periods = self._period_builder.build(guest_rates)
            ctx = PricingContext(
                booking_date=booking_date,
                loyalty_status=guest.loyalty_status,
                bank_status=guest.bank_status,
                children_4_13=guest.occupancy.children_4_13,
            )
            lines_map = self._selector.best_prices_by_date(
                daily_rates=guest_rates,
                periods=periods,
                offers=offers,
                ctx=ctx,
            )

            matched_lines: list[DateLineDTO] = []
            for cand in lines_map.values():
                if not (date_from <= cand.day <= date_to):
                    continue
                matched_lines.append(
                    DateLineDTO(
                        date=cand.day,
                        category_name=cand.category_id,
                        group_id=cand.group_id,
                        availability_period=cand.availability_period,
                        tariff_code=cand.tariff_code,
                        old_price=cand.old_price,
                        new_price=cand.new_price,
                        offer_title=cand.offer_title,
                        offer_repr=cand.offer_repr,
                        offer_min_nights=cand.offer_min_nights,
                        applied_bank_status=cand.applied_bank_status,
                        applied_bank_percent=cand.applied_bank_percent,
                        applied_loyalty_status=cand.loyalty_status,
                        applied_loyalty_percent=cand.loyalty_percent,
                        offer_id=cand.offer_id,
                    )
                )
            matched_lines.sort(key=lambda x: (x.date, x.category_name, x.tariff_code))

            best_periods: dict[str, list[PeriodPickDTO]] = {}
            target_groups = (
                guest.effective_allowed_groups
                if guest.effective_allowed_groups is not None
                else {x.group_id for x in matched_lines}
            )
            for gid in sorted(target_groups):
                picks = find_best_periods_in_group(
                    daily_rates=rates,
                    offers=offers,
                    group_rules=group_rules,
                    child_policies=child_policies,
                    guest=guest,
                    ctx=ctx,
                    group_id=gid,
                    date_from=date_from,
                    date_to=date_to,
                    top_k=5,
                )
                if picks:
                    best_periods[gid] = picks

            results.append(
                GuestResult(
                    guest_id=guest.guest_id or f"guest_{idx}",
                    guest_name=guest.guest_name,
                    matched_lines=matched_lines,
                    best_periods=best_periods,
                    desired_price_per_night=guest.desired_price_per_night,
                )
            )

        return results

    @staticmethod
    def _filter_rates_for_guest(rates, *, guest: GuestPreferences, group_rules):
        allowed_groups = guest.effective_allowed_groups
        out = []
        for rate in rates:
            if allowed_groups is not None and rate.group_id not in allowed_groups:
                continue
            if rate.adults_count != guest.occupancy.adults:
                continue
            rule = group_rules.get(rate.group_id)
            if rule is not None and not can_fit(rule, guest.occupancy):
                continue
            out.append(rate)
        return out
