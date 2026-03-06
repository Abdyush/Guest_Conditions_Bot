from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

try:
    from _runtime import ensure_project_on_sys_path, load_env_if_available
except ImportError:  # pragma: no cover
    from scripts._runtime import ensure_project_on_sys_path, load_env_if_available

ROOT = ensure_project_on_sys_path()

from src.application.dto.best_date import BestDate
from src.application.dto.date_line import DateLineDTO
from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.daily_rates_source import DailyRatesSourcePort
from src.application.presenters.telegram_notification_presenter import TelegramNotificationPresenter
from src.application.use_cases.calculate_matches_for_all_guests import CalculateMatchesForAllGuests
from src.domain.services.date_price_selector import DatePriceSelector
from src.domain.services.period_builder import PeriodBuilder
from src.domain.services.pricing_service import PricingService
from src.domain.value_objects.loyalty import LoyaltyPolicy, LoyaltyStatus
from src.infrastructure.notifiers.console_notifier import ConsoleNotifier
from src.infrastructure.repositories.csv_guests_repository import CsvGuestsRepository
from src.infrastructure.repositories.csv_offers_repository import CsvOffersRepository
from src.infrastructure.repositories.csv_rates_repository import CsvRatesRepository


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_percent(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = value.strip().replace("%", "")
    if not cleaned:
        return None
    return (Decimal(cleaned) / Decimal("100")).quantize(Decimal("0.0001"))


def _parse_adults(value: str) -> list[int]:
    out: list[int] = []
    for chunk in value.split(","):
        raw = chunk.strip()
        if not raw:
            continue
        parsed = int(raw)
        if parsed <= 0:
            raise ValueError("--selenium-adults must contain only positive integers")
        out.append(parsed)
    if not out:
        raise ValueError("--selenium-adults must contain at least one positive integer")
    return sorted(set(out))


def _record_key(record: MatchedDateRecord) -> tuple[str, date, str, str, int, str, str, str]:
    return (
        record.guest_id,
        record.date,
        record.category_name,
        record.tariff,
        record.new_price_minor,
        record.offer_id or "",
        record.bank_status or "",
        record.loyalty_status or "",
    )


def _line_belongs_to_period_record(guest_id: str, line: DateLineDTO, rec: MatchedDateRecord) -> bool:
    period_end = rec.period_end or rec.date
    same_identity = (
        guest_id == rec.guest_id
        and line.category_name == rec.category_name
        and line.tariff_code == rec.tariff
        and line.new_price.amount_minor == rec.new_price_minor
        and (line.offer_id or "") == (rec.offer_id or "")
        and ((line.applied_bank_status.value if line.applied_bank_status else "") == (rec.bank_status or ""))
        and ((line.applied_loyalty_status or "") == (rec.loyalty_status or ""))
    )
    if not same_identity:
        return False
    if not (rec.date <= line.date <= period_end):
        return False
    return line.availability_period.start == rec.availability_start and line.availability_period.end == rec.availability_end


def _line_to_record(guest_id: str, line: DateLineDTO, *, computed_at: datetime) -> MatchedDateRecord:
    return MatchedDateRecord(
        guest_id=guest_id,
        date=line.date,
        category_name=line.category_name,
        group_id=line.group_id,
        tariff=line.tariff_code,
        old_price_minor=line.old_price.amount_minor,
        new_price_minor=line.new_price.amount_minor,
        offer_id=line.offer_id,
        offer_title=line.offer_title,
        offer_repr=line.offer_repr,
        offer_min_nights=line.offer_min_nights,
        loyalty_status=line.applied_loyalty_status,
        loyalty_percent=_parse_percent(line.applied_loyalty_percent),
        bank_status=line.applied_bank_status.value if line.applied_bank_status is not None else None,
        bank_percent=line.applied_bank_percent,
        availability_start=line.availability_period.start,
        availability_end=line.availability_period.end,
        computed_at=computed_at,
        period_end=line.date,
    )


def _to_best_date(line: DateLineDTO) -> BestDate:
    return BestDate(
        date=line.date,
        category_name=line.category_name,
        group_id=line.group_id,
        availability_period=line.availability_period,
        tariff_code=line.tariff_code,
        old_price=line.old_price,
        new_price=line.new_price,
        offer_title=line.offer_title,
        offer_repr=line.offer_repr,
        offer_min_nights=line.offer_min_nights,
        loyalty_status=line.applied_loyalty_status,
        loyalty_percent=line.applied_loyalty_percent,
        offer_id=line.offer_id,
        applied_bank_status=line.applied_bank_status,
        applied_bank_percent=line.applied_bank_percent,
    )


def _new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M") + "_" + uuid4().hex[:6]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run matching pipeline from CSV sources")
    default_from = date.today()
    default_to = default_from + timedelta(days=90)
    parser.add_argument("--date-from", default=default_from.isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--date-to", default=default_to.isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--booking-date", default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--rates-csv", default=str(ROOT / "data" / "daily_rates.csv"))
    parser.add_argument("--offers-csv", default=str(ROOT / "data" / "special_offers.csv"))
    parser.add_argument("--guests-csv", default=str(ROOT / "data" / "guest_details.csv"))
    parser.add_argument("--rules-csv", default=str(ROOT / "data" / "category_rules.csv"))
    parser.add_argument("--rates-source", choices=("csv", "selenium"), default="csv")
    parser.add_argument(
        "--selenium-adults",
        default="1,2,3",
        help="Comma-separated adults_count values for Selenium rates, e.g. 1,2,3",
    )
    parser.add_argument(
        "--selenium-visible",
        action="store_true",
        help="Run Chrome with UI (headless is default).",
    )
    parser.add_argument("--selenium-wait-seconds", type=int, default=20)
    return parser


def main() -> None:
    load_env_if_available()

    args = build_parser().parse_args()
    date_from = _parse_date(args.date_from)
    date_to = _parse_date(args.date_to)
    booking_date = _parse_date(args.booking_date)

    rates_source: DailyRatesSourcePort
    if args.rates_source == "selenium":
        from src.infrastructure.sources.selenium_daily_rates_source import SeleniumDailyRatesSource

        rates_source = SeleniumDailyRatesSource(
            category_rules_csv_path=args.rules_csv,
            adults_counts=_parse_adults(args.selenium_adults),
            headless=not args.selenium_visible,
            wait_seconds=args.selenium_wait_seconds,
        )
    else:
        rates_source = CsvRatesRepository(rates_csv_path=args.rates_csv)

    csv_offers_repo = CsvOffersRepository(offers_csv_path=args.offers_csv)
    csv_guests_repo = CsvGuestsRepository(guests_csv_path=args.guests_csv)

    try:
        from src.infrastructure.repositories.postgres_daily_rates_repository import PostgresDailyRatesRepository
        from src.infrastructure.repositories.postgres_desired_matches_run_repository import PostgresDesiredMatchesRunRepository
        from src.infrastructure.repositories.postgres_guests_repository import PostgresGuestsRepository
        from src.infrastructure.repositories.postgres_matches_run_repository import PostgresMatchesRunRepository
        from src.infrastructure.repositories.postgres_notifications_repository import PostgresNotificationsRepository
        from src.infrastructure.repositories.postgres_offers_repository import PostgresOffersRepository
        from src.infrastructure.repositories.postgres_rules_repository import PostgresRulesRepository
        from src.infrastructure.repositories.postgres_user_identities_repository import PostgresUserIdentitiesRepository
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "SQLAlchemy and psycopg2 are required for persistence. Install dependencies and set DATABASE_URL in .env."
        ) from exc

    rates_repo = PostgresDailyRatesRepository()
    offers_repo = PostgresOffersRepository()
    guests_repo = PostgresGuestsRepository()
    user_identities_repo = PostgresUserIdentitiesRepository()
    rules_repo = PostgresRulesRepository()
    matches_run_repo = PostgresMatchesRunRepository()
    desired_matches_run_repo = PostgresDesiredMatchesRunRepository()
    notifications_repo = PostgresNotificationsRepository()

    notifier = ConsoleNotifier()
    presenter = TelegramNotificationPresenter()

    loyalty_policy = LoyaltyPolicy(
        {
            LoyaltyStatus.WHITE: Decimal("0.05"),
            LoyaltyStatus.BRONZE: Decimal("0.07"),
            LoyaltyStatus.SILVER: Decimal("0.08"),
            LoyaltyStatus.GOLD: Decimal("0.10"),
            LoyaltyStatus.PLATINUM: Decimal("0.12"),
            LoyaltyStatus.DIAMOND: Decimal("0.15"),
        }
    )
    # Load all CSV data into Postgres; from this point pipeline reads only from DB repositories.
    rules_repo.replace_from_csv(args.rules_csv)
    if args.rates_source == "selenium":
        synced_rates = rates_source.get_daily_rates(date_from, date_to)
    else:
        synced_rates = rates_source.get_daily_rates(date.min, date.max)
    rates_repo.replace_all(synced_rates)
    offers_repo.replace_all(csv_offers_repo.get_offers(booking_date))
    csv_guests = csv_guests_repo.get_active_guests()
    guests_repo.replace_all(csv_guests)
    for guest in csv_guests:
        if guest.guest_id and guest.guest_phone:
            user_identities_repo.upsert_identity(
                provider="phone",
                external_user_id=guest.guest_phone,
                guest_id=guest.guest_id,
            )

    pricing_service = PricingService(loyalty_policy=loyalty_policy, group_rules=rules_repo.get_group_rules(), child_policy_by_group=rules_repo.get_child_policies())
    selector = DatePriceSelector(pricing_service)

    use_case = CalculateMatchesForAllGuests(
        rates_repo=rates_repo,
        offers_repo=offers_repo,
        guests_repo=guests_repo,
        rules_repo=rules_repo,
        pricing_service=pricing_service,
        period_builder=PeriodBuilder,
        selector=selector,
    )

    run_id = _new_run_id()
    computed_at = datetime.now()

    results = use_case.execute(date_from=date_from, date_to=date_to, booking_date=booking_date)

    all_records: list[MatchedDateRecord] = []
    desired_records: list[MatchedDateRecord] = []
    for result in results:
        guest_id = result.guest_id
        for line in result.matched_lines:
            rec = _line_to_record(guest_id, line, computed_at=computed_at)
            all_records.append(rec)
            if line.new_price <= result.desired_price_per_night:
                desired_records.append(rec)

    matches_run_repo.replace_run(run_id, all_records)
    desired_matches_run_repo.replace_run(run_id, desired_records)

    new_records = notifications_repo.filter_new(desired_records, as_of_date=booking_date)
    notified_guests = 0

    new_lines_by_guest: dict[str, list[DateLineDTO]] = defaultdict(list)
    for result in results:
        for line in result.matched_lines:
            if line.new_price > result.desired_price_per_night:
                continue
            if any(_line_belongs_to_period_record(result.guest_id, line, rec) for rec in new_records):
                new_lines_by_guest[result.guest_id].append(line)

    for result in results:
        guest_lines = sorted(
            new_lines_by_guest.get(result.guest_id, []),
            key=lambda x: (x.date, x.category_name, x.tariff_code),
        )
        if not guest_lines:
            continue

        notified_guests += 1
        guest_title = result.guest_name or result.guest_id
        best_dates = [_to_best_date(x) for x in guest_lines]
        message = presenter.render_batch(best_dates, title=f"{guest_title}: suitable dates", limit=50)

        period_lines: list[str] = []
        for group_id, picks in sorted(result.best_periods.items()):
            period_lines.append(f"Best periods in group {group_id}:")
            for pick in picks:
                if pick.applied_bank_status is not None and pick.applied_bank_percent is not None:
                    bank_pct = (pick.applied_bank_percent * Decimal("100")).quantize(Decimal("1"))
                    bank_text = f"{pick.applied_bank_status.value} {bank_pct}%"
                    loyalty_text = "-"
                elif pick.applied_loyalty_status is not None and pick.applied_loyalty_percent is not None:
                    bank_text = "-"
                    loyalty_text = f"{pick.applied_loyalty_status} {pick.applied_loyalty_percent}"
                else:
                    bank_text = "-"
                    loyalty_text = "-"

                period_lines.append(
                    f"{pick.start_date.isoformat()}-{pick.end_date_inclusive.isoformat()} "
                    f"({pick.nights} nights) | {pick.category_name} | {pick.tariff_code} | {pick.new_price_per_night} "
                    f"| BANK: {bank_text} | LOYALTY: {loyalty_text}"
                )

        if period_lines:
            message = message + "\n" + "\n".join(period_lines)

        notifier.send(result.guest_id, message)

    notifications_repo.mark_sent(new_records, run_id=run_id)
    print(
        "Run summary: "
        f"run_id={run_id}, guests_total={len(results)}, "
        f"matches_total={len(all_records)}, desired_matches_total={len(desired_records)}, new_matches={len(new_records)}, "
        f"guests_notified={notified_guests}"
    )


if __name__ == "__main__":
    main()
