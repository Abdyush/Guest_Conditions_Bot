from __future__ import annotations

from src.application.dto.get_best_period_query import GetBestPeriodQuery
from src.application.dto.period_pick import PeriodPickDTO
from src.application.ports.guests_repository import GuestsRepository
from src.application.ports.offers_repository import OffersRepository
from src.application.ports.rates_repository import RatesRepository
from src.application.ports.rules_repository import RulesRepository
from src.application.use_cases.find_best_periods_in_group import find_best_periods_in_group
from src.domain.services.pricing_service import PricingContext


class GetBestPeriodsForGuestInGroup:
    def __init__(
        self,
        *,
        rates_repo: RatesRepository,
        offers_repo: OffersRepository,
        guests_repo: GuestsRepository,
        rules_repo: RulesRepository,
    ):
        self._rates_repo = rates_repo
        self._offers_repo = offers_repo
        self._guests_repo = guests_repo
        self._rules_repo = rules_repo

    def execute(self, query: GetBestPeriodQuery) -> tuple[str, list[PeriodPickDTO]]:
        guests = self._guests_repo.get_active_guests()
        guest = next((g for g in guests if g.guest_id == query.guest_id), None)
        if guest is None:
            raise ValueError(f"Guest not found: {query.guest_id}")

        rates = self._rates_repo.get_daily_rates(query.date_from, query.date_to)
        offers = self._offers_repo.get_offers(query.booking_date)
        group_rules = self._rules_repo.get_group_rules()
        child_policies = self._rules_repo.get_child_policies()

        ctx = PricingContext(
            booking_date=query.booking_date,
            loyalty_status=guest.loyalty_status,
            bank_status=guest.bank_status,
            children_4_13=guest.occupancy.children_4_13,
        )

        picks = find_best_periods_in_group(
            daily_rates=rates,
            offers=offers,
            group_rules=group_rules,
            child_policies=child_policies,
            guest=guest,
            ctx=ctx,
            group_id=query.group_id,
            date_from=query.date_from,
            date_to=query.date_to,
            top_k=query.top_k,
        )
        return query.guest_id, picks
