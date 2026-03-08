from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()

from src.domain.value_objects.discount import PayXGetY, PercentOff


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


def _discount_repr(discount) -> str:
    if isinstance(discount, PercentOff):
        pct = int((discount.percent * Decimal("100")).quantize(Decimal("1")))
        return f"PERCENT:{pct}%"
    if isinstance(discount, PayXGetY):
        return f"PAY_X_GET_Y:{discount.pay_nights}/{discount.get_nights}"
    return discount.__class__.__name__


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
        print("[trace] print-only mode: skip writing to Postgres")
    else:
        repo = PostgresOffersRepository()
        repo.replace_all(offers)
        print(f"[trace] saved to Postgres table 'special_offers': {len(offers)} rows")

    print(f"Parsed offers: {len(offers)}")
    print("id;title;discount;min_nights;stay_periods;booking_period;allowed_groups;allowed_categories;loyalty_compatible")
    for offer in offers:
        stay = "|".join(f"{p.start.isoformat()}..{p.end.isoformat()}" for p in offer.stay_periods)
        booking = f"{offer.booking_period.start.isoformat()}..{offer.booking_period.end.isoformat()}" if offer.booking_period else ""
        groups = ",".join(sorted(offer.allowed_groups)) if offer.allowed_groups else ""
        categories = "|".join(sorted(offer.allowed_categories)) if offer.allowed_categories else ""
        print(
            f"{offer.id};{offer.title};{_discount_repr(offer.discount)};{offer.min_nights or ''};"
            f"{stay};{booking};{groups};{categories};{str(offer.loyalty_compatible).lower()}"
        )


if __name__ == "__main__":
    main()
