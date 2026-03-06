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
        description="Run Selenium daily rates parser for one stay date (today by default)."
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
        help="Adults count for produced rates (default: 1).",
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


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()

    if args.adults <= 0:
        raise ValueError("--adults must be > 0")

    stay_date = date.fromisoformat(args.stay_date)
    from src.infrastructure.sources.selenium_daily_rates_source import SeleniumDailyRatesSource

    source = SeleniumDailyRatesSource(
        category_rules_csv_path=args.rules_csv,
        adults_counts=[args.adults],
        headless=not args.visible,
        wait_seconds=args.wait_seconds,
    )

    rates = source.get_daily_rates(stay_date, stay_date)
    print(f"Parsed rates: {len(rates)} rows")
    print("date;category_name;group_id;tariff_code;adults_count;amount_minor;currency;is_last_room")
    for r in rates:
        print(
            f"{r.date.isoformat()};{r.category_id};{r.group_id};{r.tariff_code};"
            f"{r.adults_count};{r.price.amount_minor};{r.price.currency};{str(r.is_last_room).lower()}"
        )


if __name__ == "__main__":
    main()
