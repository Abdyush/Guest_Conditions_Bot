from __future__ import annotations

import argparse
from datetime import date

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run 6 parallel Selenium rates parsers (adults 1..6) for a date window."
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
        help="Comma-separated adults counts for parallel runs (default: 1,2,3,4,5,6).",
    )
    parser.add_argument(
        "--rules-csv",
        default=str(ROOT / "data" / "category_rules.csv"),
        help="Path to category rules CSV for group mapping.",
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

    from src.infrastructure.selenium.rates_parallel_runner import (
        RatesParallelRunConfig,
        SeleniumRatesParallelRunner,
    )

    config = RatesParallelRunConfig(
        category_rules_csv_path=args.rules_csv,
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
