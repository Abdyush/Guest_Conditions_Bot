from __future__ import annotations

import argparse
from datetime import date

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Selenium offers parser from legacy offers_funcs and print mapped offers.")
    parser.add_argument("--today", default=date.today().isoformat(), help="Booking date in YYYY-MM-DD format.")
    parser.add_argument("--rules-csv", default=str(ROOT / "data" / "category_rules.csv"))
    parser.add_argument("--visible", action="store_true", help="Run Chrome with GUI.")
    parser.add_argument("--wait-seconds", type=int, default=20)
    parser.add_argument("--fail-fast", action="store_true", help="Stop if some offers fail to map.")
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Only print parsed offers, do not write to Postgres.",
    )
    return parser


def main() -> None:
    load_env_if_available()
    args = build_parser().parse_args()

    from src.infrastructure.sources.selenium_offers_source import SeleniumOffersSource
    from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository

    source = SeleniumOffersSource(
        category_rules_csv_path=args.rules_csv,
        headless=not args.visible,
        wait_seconds=args.wait_seconds,
        fail_fast=args.fail_fast,
    )
    offers = source.get_offers(date.fromisoformat(args.today))

    if args.print_only:
        print("Режим print-only: запись в Postgres пропущена")
    else:
        repo = PostgresOffersRepository()
        repo.replace_all(offers)
        print(f"Данные спецпредложений сохранены в Postgres: {len(offers)} записей")


if __name__ == "__main__":
    main()
