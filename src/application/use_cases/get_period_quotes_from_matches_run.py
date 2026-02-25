from __future__ import annotations

from collections import defaultdict

from src.application.dto.get_period_quotes_query import GetPeriodQuotesQuery
from src.application.dto.period_quote import PeriodQuote
from src.application.ports.matches_run_repository import MatchesRunRepository


class GetPeriodQuotesFromMatchesRun:
    def __init__(self, repo: MatchesRunRepository):
        self._repo = repo

    def execute(self, query: GetPeriodQuotesQuery) -> tuple[str, list[PeriodQuote]]:
        selected_run = query.run_id or self._repo.get_latest_run_id()
        if not selected_run:
            return "", []

        rows = self._repo.get_run_rows(selected_run)
        rows = [r for r in rows if r.guest_id == query.guest_id]
        if query.group_ids:
            rows = [r for r in rows if r.group_id in query.group_ids]

        agg: dict[tuple, dict[str, int]] = defaultdict(lambda: {"old": 0, "new": 0, "nights": 0})

        for row in rows:
            row_start = row.date
            row_end = row.period_end or row.date

            overlap_start = max(query.period_start, row_start)
            overlap_end = min(query.period_end, row_end)
            if overlap_end < overlap_start:
                continue

            nights = (overlap_end - overlap_start).days + 1
            key = (
                row.category_name,
                row.group_id,
                row.tariff,
                overlap_start,
                overlap_end,
                row.offer_id,
                row.offer_title,
                row.offer_repr,
                row.loyalty_status,
                str(row.loyalty_percent) if row.loyalty_percent is not None else None,
                row.bank_status,
                str(row.bank_percent) if row.bank_percent is not None else None,
            )
            agg[key]["old"] += row.old_price_minor * nights
            agg[key]["new"] += row.new_price_minor * nights
            agg[key]["nights"] += nights

        quotes: list[PeriodQuote] = []
        for (
            category_name,
            group_id,
            tariff,
            applied_from,
            applied_to,
            offer_id,
            offer_title,
            offer_repr,
            loyalty_status,
            loyalty_percent,
            bank_status,
            bank_percent,
        ), totals in agg.items():
            quotes.append(
                PeriodQuote(
                    category_name=category_name,
                    group_id=group_id,
                    tariff=tariff,
                    from_date=query.period_start,
                    to_date=query.period_end,
                    applied_from=applied_from,
                    applied_to=applied_to,
                    nights=totals["nights"],
                    total_old_minor=totals["old"],
                    total_new_minor=totals["new"],
                    offer_id=offer_id,
                    offer_title=offer_title,
                    offer_repr=offer_repr,
                    loyalty_status=loyalty_status,
                    loyalty_percent=loyalty_percent,
                    bank_status=bank_status,
                    bank_percent=bank_percent,
                )
            )

        quotes.sort(key=lambda x: (x.group_id, x.category_name, x.tariff, x.applied_from))
        return selected_run, quotes
