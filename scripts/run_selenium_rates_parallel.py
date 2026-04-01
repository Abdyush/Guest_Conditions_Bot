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
            "Full manual rates parser utility: run the current parallel Selenium rates "
            "parser stack for a date window and one or more adults counts."
        ),
        epilog=(
            "For a narrower single-date/single-adult smoke check, "
            "use scripts/run_selenium_rates.py."
        ),
    )
    parser.add_argument(
        "--start-date",
        default=date.today().isoformat(),
        help="Start stay date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--days-to-collect",
        type=int,
        default=3,
        help="How many consecutive days to collect from start date (default: 3).",
    )
    parser.add_argument(
        "--adults",
        default="1,2,3,4,5,6",
        help="Comma-separated adults counts for the full manual parser run (default: 1,2,3,4,5,6).",
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


def _parse_adults(value: str) -> tuple[int, ...]:
    out: list[int] = []
    for raw in value.split(","):
        cleaned = raw.strip()
        if not cleaned:
            continue
        parsed = int(cleaned)
        if parsed <= 0:
            raise ValueError("--adults must contain only positive integers")
        out.append(parsed)
    if not out:
        raise ValueError("--adults must contain at least one value")
    return tuple(sorted(set(out)))


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()

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

    config = RatesParallelRunConfig(
        category_to_group=category_to_group,
        adults_counts=_parse_adults(args.adults),
        days_to_collect=args.days_to_collect,
        headless=not args.visible,
        wait_seconds=args.wait_seconds,
    )
    runner = SeleniumRatesParallelRunner(config)
    rates = runner.run(start_date=date.fromisoformat(args.start_date))

    print(f"ИТОГО: собрано {len(rates)} строк тарифов")


if __name__ == "__main__":
    main()
