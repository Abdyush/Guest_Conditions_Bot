from __future__ import annotations

import argparse
from datetime import date

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ensure_project_on_sys_path()

from src.application.use_cases.get_period_quotes_from_matches_run import GetPeriodQuotesFromMatchesRun
from src.application.dto.get_period_quotes_query import GetPeriodQuotesQuery
from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _format_minor(value: int) -> str:
    rub = value / 100
    return f"{rub:.2f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Get guest quotes for selected period from matches_run")
    parser.add_argument("--guest-id", required=True, help="Guest ID, e.g. G1")
    parser.add_argument("--date-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="YYYY-MM-DD")
    parser.add_argument("--groups", default="", help="Comma-separated group ids, e.g. DELUXE,VILLA")
    parser.add_argument("--run-id", default="", help="Optional run_id. If empty, latest run is used")
    return parser


def main() -> None:
    load_env_if_available()

    args = build_parser().parse_args()
    date_from = _parse_date(args.date_from)
    date_to = _parse_date(args.date_to)
    group_ids = {x.strip() for x in args.groups.split(",") if x.strip()} or None
    run_id = args.run_id.strip() or None

    repo = PostgresMatchesRunRepository()
    use_case = GetPeriodQuotesFromMatchesRun(repo)
    query = GetPeriodQuotesQuery(
        guest_id=args.guest_id,
        period_start=date_from,
        period_end=date_to,
        group_ids=group_ids,
        run_id=run_id,
    )
    selected_run, quotes = use_case.execute(query)

    if not selected_run:
        print("No runs found in matches_run.")
        return

    print(f"run_id={selected_run}")
    print(
        "guest_id;period;applied_period;offer_period;category_name;group_id;tariff;nights;total_old_rub;total_new_rub;"
        "offer_id;offer_title;offer_repr;loyalty_status;loyalty_percent;bank_status;bank_percent"
    )
    period_text = f"{date_from.isoformat()} - {date_to.isoformat()}"
    for q in quotes:
        applied_period = f"{q.applied_from.isoformat()} - {q.applied_to.isoformat()}"
        offer_period = applied_period if q.offer_id else ""
        print(
            f"{args.guest_id};{period_text};{applied_period};{offer_period};{q.category_name};{q.group_id};{q.tariff};{q.nights};"
            f"{_format_minor(q.total_old_minor)};{_format_minor(q.total_new_minor)};"
            f"{q.offer_id or ''};{q.offer_title or ''};{q.offer_repr or ''};"
            f"{q.loyalty_status or ''};{q.loyalty_percent or ''};{q.bank_status or ''};{q.bank_percent or ''}"
        )


if __name__ == "__main__":
    main()
