from __future__ import annotations

import argparse
from datetime import date, timedelta

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ensure_project_on_sys_path()

from src.application.dto.get_best_period_query import GetBestPeriodQuery
from src.application.use_cases.get_best_periods_for_guest_in_group import GetBestPeriodsForGuestInGroup
from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
from src.infrastructure.repositories.postgres_guests_repository import PostgresGuestsRepository
from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Get best period(s) for guest in selected category group")
    default_from = date.today()
    default_to = default_from + timedelta(days=90)
    parser.add_argument("--guest-id", required=True, help="Guest ID, e.g. G1")
    parser.add_argument("--group-id", required=True, help="Group ID, e.g. DELUXE")
    parser.add_argument("--date-from", default=default_from.isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--date-to", default=default_to.isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--booking-date", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--top-k", type=int, default=1)
    return parser


def main() -> None:
    load_env_if_available()

    args = build_parser().parse_args()
    query = GetBestPeriodQuery(
        guest_id=args.guest_id,
        group_id=args.group_id,
        date_from=_parse_date(args.date_from),
        date_to=_parse_date(args.date_to),
        booking_date=_parse_date(args.booking_date),
        top_k=args.top_k,
    )

    use_case = GetBestPeriodsForGuestInGroup(
        rates_repo=PostgresDailyRatesRepository(),
        offers_repo=PostgresOffersRepository(),
        guests_repo=PostgresGuestsRepository(),
        rules_repo=PostgresRulesRepository(),
    )

    guest_id, picks = use_case.execute(query)
    print(f"guest_id={guest_id};group_id={query.group_id};date_range={query.date_from.isoformat()} - {query.date_to.isoformat()}")
    print("rank;start_date;end_date;nights;category_name;tariff;new_price_per_night;offer;loyalty;bank")

    if not picks:
        return

    for idx, pick in enumerate(picks, start=1):
        offer = pick.offer_title or "-"
        loyalty = (
            f"{pick.applied_loyalty_status} {pick.applied_loyalty_percent}"
            if pick.applied_loyalty_status is not None and pick.applied_loyalty_percent is not None
            else "-"
        )
        bank = (
            f"{pick.applied_bank_status.value} {pick.applied_bank_percent}"
            if pick.applied_bank_status is not None and pick.applied_bank_percent is not None
            else "-"
        )
        print(
            f"{idx};{pick.start_date.isoformat()};{pick.end_date_inclusive.isoformat()};{pick.nights};"
            f"{pick.category_name};{pick.tariff_code};{pick.new_price_per_night};{offer};{loyalty};{bank}"
        )


if __name__ == "__main__":
    main()
