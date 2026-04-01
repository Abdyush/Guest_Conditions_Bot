from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke/inspection utility: run the current Selenium rates parser stack "
            "for one stay date and one adults count."
        ),
        epilog=(
            "For a fuller manual parser run across multiple dates and adults counts, "
            "use scripts/run_selenium_rates_parallel.py."
        ),
    )
    parser.add_argument(
        "--stay-date",
        default=date.today().isoformat(),
        help="Stay date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--adults",
        type=int,
        default=1,
        help="Adults count for the single smoke run (default: 1).",
    )
    parser.add_argument(
        "--rules-csv",
        default="",
        help="Deprecated and ignored. Category rules are loaded from Postgres.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run Chrome with GUI. By default parser runs in headless mode.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=20,
        help="WebDriverWait timeout in seconds.",
    )
    return parser


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()

    if args.adults <= 0:
        raise ValueError("--adults must be > 0")

    stay_date = date.fromisoformat(args.stay_date)
    from src.infrastructure.loaders.category_rules_loader import load_category_rules
    from src.infrastructure.selenium.rates_parallel_runner import (
        RatesParallelRunConfig,
        SeleniumRatesParallelRunner,
    )
    from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository

    rules_csv_path = Path(args.rules_csv) if args.rules_csv else ROOT / "data" / "category_rules.csv"
    try:
        category_to_group = PostgresRulesRepository().get_category_to_group()
    except Exception as exc:
        if not rules_csv_path.exists():
            raise RuntimeError(
                f"Failed to load category rules from Postgres ({exc}) and CSV fallback was not found: {rules_csv_path}"
            ) from exc
        category_to_group, _, _ = load_category_rules(rules_csv_path)
        print(f"WARNING: Postgres category rules unavailable, using CSV fallback: {rules_csv_path}")

    runner = SeleniumRatesParallelRunner(
        RatesParallelRunConfig(
            category_to_group=category_to_group,
            adults_counts=(args.adults,),
            days_to_collect=1,
            headless=not args.visible,
            wait_seconds=args.wait_seconds,
        )
    )
    rates = runner.run(start_date=stay_date)
    print(f"Parsed rates: {len(rates)} rows")
    print("date;category_name;group_id;tariff_code;adults_count;amount_minor;currency;is_last_room")
    for r in rates:
        print(
            f"{r.date.isoformat()};{r.category_id};{r.group_id};{r.tariff_code};"
            f"{r.adults_count};{r.price.amount_minor};{r.price.currency};{str(r.is_last_room).lower()}"
        )


if __name__ == "__main__":
    main()
