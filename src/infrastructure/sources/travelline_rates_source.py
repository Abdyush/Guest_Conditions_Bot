from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from time import perf_counter

from src.application.ports.daily_rates_source import DailyRatesSourcePort
from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway
from src.infrastructure.travelline.models import (
    TravellineAdultsProcessingSummary,
    TravellineCollectionDiagnostics,
    TravellineCollectionResult,
    TravellineDateRowsStat,
    TravellineRatesTransformResult,
)
from src.infrastructure.travelline.rates_transform import (
    map_hotel_info_to_room_types,
    map_raw_availability_to_quotes,
    transform_travelline_quotes_to_daily_rates,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TravellineRatesSource(DailyRatesSourcePort):
    hotel_code: str
    hotel_info_gateway: TravellineHotelInfoGateway
    availability_gateway: TravellineAvailabilityGateway
    category_to_group: dict[str, str]
    adults_counts: tuple[int, ...] = (1,)

    def get_daily_rates(self, date_from: date, date_to: date) -> list:
        result = self.collect_window(date_from=date_from, date_to=date_to, adults_counts=self.adults_counts)
        return list(result.daily_rates)

    def collect_window_with_diagnostics(
        self,
        *,
        date_from: date,
        date_to: date,
        adults_counts: tuple[int, ...],
        fail_fast: bool,
    ) -> TravellineCollectionResult:
        started_at = perf_counter()
        expected_dates = self._build_expected_dates(date_from=date_from, date_to=date_to)
        total_dates = len(expected_dates)
        total_adults = len(adults_counts)
        total_requests = total_dates * total_adults
        adults_stats = {
            adults: {
                "expected_requests_count": len(expected_dates),
                "attempted_count": 0,
                "success_count": 0,
                "fail_count": 0,
            }
            for adults in adults_counts
        }
        collection_failure_reasons: list[str] = []
        raw_quotes = []

        logger.info(
            "travelline_collection_started hotel_code=%s date_from=%s date_to=%s dates=%s adults_counts=%s expected_requests=%s fail_fast=%s",
            self.hotel_code,
            date_from.isoformat(),
            date_to.isoformat(),
            total_dates,
            list(adults_counts),
            total_requests,
            fail_fast,
        )

        try:
            room_types = map_hotel_info_to_room_types(
                self.hotel_info_gateway.fetch_raw_hotel_info(hotel_code=self.hotel_code)
            )
        except Exception as exc:
            if fail_fast:
                raise
            collection_failure_reasons.append(f"hotel_info_fetch_failed:{type(exc).__name__}")
            room_types = {}

        if room_types or not collection_failure_reasons:
            current = date_from
            date_index = 0
            while current <= date_to:
                date_index += 1
                checkout = current + timedelta(days=1)
                logger.info(
                    "travelline_collection_date_progress date=%s checkout=%s date_index=%s/%s adults_total=%s",
                    current.isoformat(),
                    checkout.isoformat(),
                    date_index,
                    total_dates,
                    total_adults,
                )
                for adults_index, adults in enumerate(adults_counts, start=1):
                    stats = adults_stats[adults]
                    stats["attempted_count"] += 1
                    request_started_at = perf_counter()
                    try:
                        raw_payload = self.availability_gateway.fetch_raw_one_night_availability(
                            hotel_code=self.hotel_code,
                            check_in=current,
                            check_out=checkout,
                            adults=adults,
                        )
                    except Exception as exc:
                        stats["fail_count"] += 1
                        reason = (
                            f"availability_fetch_failed:date={current.isoformat()}:adults={adults}:"
                            f"{type(exc).__name__}"
                        )
                        collection_failure_reasons.append(reason)
                        logger.warning(
                            "travelline_collection_request_failed date=%s adults=%s adults_index=%s/%s attempted=%s success=%s fail=%s elapsed_seconds=%.2f reason=%s",
                            current.isoformat(),
                            adults,
                            adults_index,
                            total_adults,
                            stats["attempted_count"],
                            stats["success_count"],
                            stats["fail_count"],
                            perf_counter() - request_started_at,
                            type(exc).__name__,
                        )
                        if fail_fast:
                            raise
                        continue

                    stats["success_count"] += 1
                    quotes_before = len(raw_quotes)
                    raw_quotes.extend(
                        map_raw_availability_to_quotes(
                            raw_payload,
                            hotel_code=self.hotel_code,
                            check_in=current,
                            check_out=checkout,
                            adults=adults,
                            room_types=room_types,
                        )
                    )
                    logger.info(
                        "travelline_collection_request_complete date=%s adults=%s adults_index=%s/%s attempted=%s success=%s fail=%s quotes_added=%s total_quotes=%s elapsed_seconds=%.2f",
                        current.isoformat(),
                        adults,
                        adults_index,
                        total_adults,
                        stats["attempted_count"],
                        stats["success_count"],
                        stats["fail_count"],
                        len(raw_quotes) - quotes_before,
                        len(raw_quotes),
                        perf_counter() - request_started_at,
                    )
                current = current + timedelta(days=1)

        transform_result = transform_travelline_quotes_to_daily_rates(
            raw_quotes=raw_quotes,
            category_to_group=self.category_to_group,
        )
        adults_summaries = self._build_adults_summaries(
            adults_counts=adults_counts,
            adults_stats=adults_stats,
            transform_result=transform_result,
        )
        per_date_rows = self._build_per_date_rows(transform_result=transform_result)
        actual_dates = {item.stay_date for item in per_date_rows}
        empty_dates = tuple(stay_date for stay_date in expected_dates if stay_date not in actual_dates)
        diagnostics = TravellineCollectionDiagnostics(
            expected_dates=tuple(expected_dates),
            adults_summaries=tuple(adults_summaries),
            empty_dates=empty_dates,
            per_date_rows=tuple(per_date_rows),
            collection_failure_reasons=tuple(collection_failure_reasons),
        )
        self._log_collection_diagnostics(diagnostics=diagnostics)
        logger.info(
            "travelline_collection_finished raw_quotes=%s daily_rates=%s elapsed_seconds=%.2f",
            len(raw_quotes),
            len(transform_result.daily_rates),
            perf_counter() - started_at,
        )
        return TravellineCollectionResult(
            transform_result=transform_result,
            diagnostics=diagnostics,
        )

    def collect_window(
        self,
        *,
        date_from: date,
        date_to: date,
        adults_counts: tuple[int, ...],
    ) -> TravellineRatesTransformResult:
        return self.collect_window_with_diagnostics(
            date_from=date_from,
            date_to=date_to,
            adults_counts=adults_counts,
            fail_fast=True,
        ).transform_result

    @staticmethod
    def _build_expected_dates(*, date_from: date, date_to: date) -> list[date]:
        out: list[date] = []
        current = date_from
        while current <= date_to:
            out.append(current)
            current = current + timedelta(days=1)
        return out

    @staticmethod
    def _build_per_date_rows(
        *,
        transform_result: TravellineRatesTransformResult,
    ) -> list[TravellineDateRowsStat]:
        rows_by_date: dict[date, int] = {}
        for rate in transform_result.daily_rates:
            rows_by_date[rate.date] = rows_by_date.get(rate.date, 0) + 1
        return [
            TravellineDateRowsStat(stay_date=stay_date, rows_count=rows_count)
            for stay_date, rows_count in sorted(rows_by_date.items())
        ]

    @staticmethod
    def _build_adults_summaries(
        *,
        adults_counts: tuple[int, ...],
        adults_stats: dict[int, dict[str, int]],
        transform_result: TravellineRatesTransformResult,
    ) -> list[TravellineAdultsProcessingSummary]:
        rows_by_adults: dict[int, int] = {}
        for rate in transform_result.daily_rates:
            rows_by_adults[rate.adults_count] = rows_by_adults.get(rate.adults_count, 0) + 1

        out: list[TravellineAdultsProcessingSummary] = []
        for adults in adults_counts:
            stats = adults_stats[adults]
            rows_count = rows_by_adults.get(adults, 0)
            expected_requests_count = stats["expected_requests_count"]
            attempted_count = stats["attempted_count"]
            success_count = stats["success_count"]
            fail_count = stats["fail_count"]
            if attempted_count == 0:
                status = "not_attempted"
            elif fail_count > 0 or attempted_count < expected_requests_count or success_count < expected_requests_count:
                status = "attempt_failed"
            elif rows_count == 0:
                status = "completed_zero_rows"
            else:
                status = "completed_with_rows"
            out.append(
                TravellineAdultsProcessingSummary(
                    adults_count=adults,
                    expected_requests_count=expected_requests_count,
                    attempted_count=attempted_count,
                    success_count=success_count,
                    fail_count=fail_count,
                    collected_final_rows_count=rows_count,
                    status=status,
                )
            )
        return out

    @staticmethod
    def _log_collection_diagnostics(*, diagnostics: TravellineCollectionDiagnostics) -> None:
        logger.info(
            "travelline_collection_summary expected_dates=%s actual_dates=%s empty_dates=%s failures=%s",
            len(diagnostics.expected_dates),
            len(diagnostics.per_date_rows),
            len(diagnostics.empty_dates),
            len(diagnostics.collection_failure_reasons),
        )
        for item in diagnostics.adults_summaries:
            logger.info(
                "travelline_collection_adults adults=%s expected=%s attempted=%s success=%s fail=%s rows=%s status=%s",
                item.adults_count,
                item.expected_requests_count,
                item.attempted_count,
                item.success_count,
                item.fail_count,
                item.collected_final_rows_count,
                item.status,
            )
            if item.status == "completed_zero_rows":
                logger.warning(
                    "travelline_collection_zero_rows adults=%s expected=%s",
                    item.adults_count,
                    item.expected_requests_count,
                )
