from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from src.application.dto.travelline_publish_report import (
    TravellinePublishAdultsSummary,
    TravellinePublishDateStat,
    TravellinePublishRunReport,
)
from src.application.ports.travelline_publish_report_repository import TravellinePublishReportRepository
from src.application.ports.rates_repository import RatesRepository
from src.domain.entities.rate import DailyRate
from src.infrastructure.sources.travelline_rates_source import TravellineRatesSource
from src.infrastructure.travelline.models import (
    TravellineCollectionDiagnostics,
    TravellineCollectionResult,
    TravellineRatesTransformResult,
)

logger = logging.getLogger(__name__)


class TravellinePublishRunError(RuntimeError):
    def __init__(self, message: str, *, report: TravellinePublishRunReport):
        super().__init__(message)
        self.report = report


class TravellinePublishValidationError(TravellinePublishRunError):
    pass


@dataclass(frozen=True, slots=True)
class TravellineCompareSummary:
    date_from: date
    date_to: date
    adults_counts: tuple[int, ...]
    selenium_total_rows: int
    travelline_total_rows: int
    selenium_only_rows: int
    travelline_only_rows: int
    exact_price_matches: int
    price_mismatches: int
    unmapped_categories: int
    tariff_pairing_anomalies: int
    duplicates_removed: int
    summary_path: str
    diff_path: str
    travelline_rates_path: str


@dataclass(frozen=True, slots=True)
class TravellineCompareRunResult:
    summary: TravellineCompareSummary
    transform_result: TravellineRatesTransformResult


@dataclass(frozen=True, slots=True)
class TravellinePublishValidationSummary:
    rows_count: int
    tariff_pairing_anomalies: int
    unmapped_categories: int
    is_valid: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TravellineRatesParserRunner:
    source: TravellineRatesSource
    rates_repo: RatesRepository
    report_repo: TravellinePublishReportRepository | None = None
    artifacts_dir: Path = Path("artifacts") / "compare"
    max_tariff_pairing_anomalies: int = 0
    max_unmapped_categories: int = 0

    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int:
        if days_to_collect <= 0:
            raise ValueError("days_to_collect must be > 0")
        started_at = perf_counter()
        date_to = start_date + timedelta(days=days_to_collect - 1)
        created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info(
            "travelline_publish_started start_date=%s date_to=%s days_to_collect=%s adults_counts=%s",
            start_date.isoformat(),
            date_to.isoformat(),
            days_to_collect,
            list(adults_counts),
        )
        try:
            collection_result = self.source.collect_window_with_diagnostics(
                date_from=start_date,
                date_to=date_to,
                adults_counts=adults_counts,
                fail_fast=False,
            )
        except Exception as exc:
            report = self._build_exception_run_report(
                start_date=start_date,
                date_to=date_to,
                adults_counts=adults_counts,
                created_at=created_at,
                reason=f"collection_exception:{type(exc).__name__}",
            )
            self._save_report(report)
            logger.exception(
                "travelline_publish_failed elapsed_seconds=%.2f",
                perf_counter() - started_at,
            )
            raise TravellinePublishRunError("travelline_publish_collection_error", report=report) from exc
        validation = self.validate_publish_candidate(collection_result=collection_result)
        logger.info(
            "travelline_publish_validation rows=%s anomalies=%s unmapped=%s is_valid=%s reasons=%s",
            validation.rows_count,
            validation.tariff_pairing_anomalies,
            validation.unmapped_categories,
            validation.is_valid,
            list(validation.failure_reasons),
        )
        report = self._build_publish_run_report(
            collection_result=collection_result,
            validation=validation,
            created_at=created_at,
            fallback_used=False,
        )
        if not validation.is_valid:
            self._save_report(report)
            logger.warning(
                "travelline_publish_finished status=failed elapsed_seconds=%.2f",
                perf_counter() - started_at,
            )
            raise TravellinePublishValidationError(
                "travelline_publish_validation_failed "
                f"rows={validation.rows_count} "
                f"tariff_pairing_anomalies={validation.tariff_pairing_anomalies} "
                f"unmapped_categories={validation.unmapped_categories}",
                report=report,
            )
        daily_rates = list(collection_result.transform_result.daily_rates)
        try:
            self.rates_repo.replace_all(daily_rates)
        except Exception as exc:
            failed_report = TravellinePublishRunReport(
                run_id=report.run_id,
                created_at=report.created_at,
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                mode=report.mode,
                validation_status="failed",
                validation_failure_reasons=report.validation_failure_reasons + (f"publish_exception:{type(exc).__name__}",),
                fallback_used=report.fallback_used,
                expected_dates_count=report.expected_dates_count,
                actual_dates_count=report.actual_dates_count,
                dates_with_no_categories_count=report.dates_with_no_categories_count,
                total_final_rows_count=report.total_final_rows_count,
                tariff_pairing_anomalies_count=report.tariff_pairing_anomalies_count,
                unmapped_categories_count=report.unmapped_categories_count,
                adults_summaries=report.adults_summaries,
                empty_dates=report.empty_dates,
                per_date_rows=report.per_date_rows,
            )
            self._save_report(failed_report)
            logger.exception(
                "travelline_publish_failed elapsed_seconds=%.2f",
                perf_counter() - started_at,
            )
            raise TravellinePublishRunError("travelline_publish_persist_error", report=failed_report) from exc
        self._save_report(report)
        logger.info(
            "travelline_publish_rows=%s elapsed_seconds=%.2f",
            len(daily_rates),
            perf_counter() - started_at,
        )
        return len(daily_rates)

    def run_compare_only(
        self,
        *,
        date_from: date,
        date_to: date,
        adults_counts: tuple[int, ...],
    ) -> TravellineCompareRunResult:
        transform_result = self.source.collect_window(
            date_from=date_from,
            date_to=date_to,
            adults_counts=adults_counts,
        )
        selenium_rates = self.rates_repo.get_daily_rates(date_from, date_to)
        summary = self._write_compare_artifacts(
            selenium_rates=selenium_rates,
            travelline_rates=list(transform_result.daily_rates),
            transform_result=transform_result,
            date_from=date_from,
            date_to=date_to,
            adults_counts=adults_counts,
        )
        return TravellineCompareRunResult(summary=summary, transform_result=transform_result)

    def validate_publish_candidate(
        self,
        *,
        collection_result: TravellineCollectionResult,
    ) -> TravellinePublishValidationSummary:
        transform_result = collection_result.transform_result
        diagnostics = collection_result.diagnostics
        rows_count = len(transform_result.daily_rates)
        tariff_pairing_anomalies = len(transform_result.tariff_pairing_anomalies)
        unmapped_categories = len(transform_result.category_mapping_mismatches)
        failure_reasons: list[str] = list(diagnostics.collection_failure_reasons)
        for item in diagnostics.adults_summaries:
            if item.status in {"not_attempted", "attempt_failed"}:
                failure_reasons.append(f"adults_{item.adults_count}:{item.status}")
        if tariff_pairing_anomalies > self.max_tariff_pairing_anomalies:
            failure_reasons.append(
                f"tariff_pairing_anomalies_exceeded:{tariff_pairing_anomalies}>{self.max_tariff_pairing_anomalies}"
            )
        if unmapped_categories > self.max_unmapped_categories:
            failure_reasons.append(
                f"unmapped_categories_exceeded:{unmapped_categories}>{self.max_unmapped_categories}"
            )
        is_valid = len(failure_reasons) == 0
        return TravellinePublishValidationSummary(
            rows_count=rows_count,
            tariff_pairing_anomalies=tariff_pairing_anomalies,
            unmapped_categories=unmapped_categories,
            is_valid=is_valid,
            failure_reasons=tuple(failure_reasons),
        )

    def mark_fallback_used(self, *, report: TravellinePublishRunReport) -> None:
        if self.report_repo is None:
            return
        self.report_repo.mark_fallback_used(run_id=report.run_id)

    def _save_report(self, report: TravellinePublishRunReport) -> None:
        if self.report_repo is None:
            return
        self.report_repo.save_run_report(report=report)

    def _build_publish_run_report(
        self,
        *,
        collection_result: TravellineCollectionResult,
        validation: TravellinePublishValidationSummary,
        created_at: datetime,
        fallback_used: bool,
    ) -> TravellinePublishRunReport:
        diagnostics = collection_result.diagnostics
        transform_result = collection_result.transform_result
        actual_dates_count = len(diagnostics.per_date_rows)
        report = TravellinePublishRunReport(
            run_id=f"tlpub_{uuid4().hex}",
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            mode="travelline_publish",
            validation_status="passed" if validation.is_valid else "failed",
            validation_failure_reasons=validation.failure_reasons,
            fallback_used=fallback_used,
            expected_dates_count=len(diagnostics.expected_dates),
            actual_dates_count=actual_dates_count,
            dates_with_no_categories_count=len(diagnostics.empty_dates),
            total_final_rows_count=len(transform_result.daily_rates),
            tariff_pairing_anomalies_count=len(transform_result.tariff_pairing_anomalies),
            unmapped_categories_count=len(transform_result.category_mapping_mismatches),
            adults_summaries=tuple(
                TravellinePublishAdultsSummary(
                    adults_count=item.adults_count,
                    expected_requests_count=item.expected_requests_count,
                    attempted_count=item.attempted_count,
                    success_count=item.success_count,
                    fail_count=item.fail_count,
                    collected_final_rows_count=item.collected_final_rows_count,
                    status=item.status,
                )
                for item in diagnostics.adults_summaries
            ),
            empty_dates=tuple(diagnostics.empty_dates),
            per_date_rows=tuple(
                TravellinePublishDateStat(
                    stay_date=item.stay_date,
                    rows_count=item.rows_count,
                )
                for item in diagnostics.per_date_rows
            ),
        )
        self._log_publish_report(report=report, diagnostics=diagnostics)
        return report

    @staticmethod
    def _build_exception_run_report(
        *,
        start_date: date,
        date_to: date,
        adults_counts: tuple[int, ...],
        created_at: datetime,
        reason: str,
    ) -> TravellinePublishRunReport:
        expected_dates = []
        current = start_date
        while current <= date_to:
            expected_dates.append(current)
            current = current + timedelta(days=1)
        return TravellinePublishRunReport(
            run_id=f"tlpub_{uuid4().hex}",
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            mode="travelline_publish",
            validation_status="failed",
            validation_failure_reasons=(reason,),
            fallback_used=False,
            expected_dates_count=len(expected_dates),
            actual_dates_count=0,
            dates_with_no_categories_count=0,
            total_final_rows_count=0,
            tariff_pairing_anomalies_count=0,
            unmapped_categories_count=0,
            adults_summaries=tuple(
                TravellinePublishAdultsSummary(
                    adults_count=adults,
                    expected_requests_count=len(expected_dates),
                    attempted_count=0,
                    success_count=0,
                    fail_count=0,
                    collected_final_rows_count=0,
                    status="not_attempted",
                )
                for adults in adults_counts
            ),
            empty_dates=tuple(),
            per_date_rows=tuple(),
        )

    @staticmethod
    def _log_publish_report(
        *,
        report: TravellinePublishRunReport,
        diagnostics: TravellineCollectionDiagnostics,
    ) -> None:
        logger.info(
            "travelline_publish_report_summary status=%s rows=%s expected_dates=%s actual_dates=%s "
            "empty_dates=%s anomalies=%s unmapped=%s fallback_used=%s",
            report.validation_status,
            report.total_final_rows_count,
            report.expected_dates_count,
            report.actual_dates_count,
            report.dates_with_no_categories_count,
            report.tariff_pairing_anomalies_count,
            report.unmapped_categories_count,
            report.fallback_used,
        )
        if report.validation_failure_reasons:
            logger.warning(
                "travelline_publish_report_failures reasons=%s",
                list(report.validation_failure_reasons),
            )
        for item in report.adults_summaries:
            logger.info(
                "travelline_publish_adults adults=%s expected=%s attempted=%s success=%s fail=%s rows=%s status=%s",
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
                    "travelline_publish_zero_rows adults=%s",
                    item.adults_count,
                )
        if diagnostics.empty_dates:
            preview = ", ".join(stay_date.isoformat() for stay_date in diagnostics.empty_dates[:10])
            logger.warning(
                "travelline_publish_empty_dates count=%s preview=%s",
                len(diagnostics.empty_dates),
                preview,
            )

    def _write_compare_artifacts(
        self,
        *,
        selenium_rates: list[DailyRate],
        travelline_rates: list[DailyRate],
        transform_result: TravellineRatesTransformResult,
        date_from: date,
        date_to: date,
        adults_counts: tuple[int, ...],
    ) -> TravellineCompareSummary:
        artifacts_dir = Path(self.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        summary_path = artifacts_dir / "travelline_vs_selenium_summary.json"
        diff_path = artifacts_dir / "travelline_vs_selenium_diff.csv"
        travelline_rates_path = artifacts_dir / "travelline_rates.csv"

        selenium_map = {_business_key(rate): rate for rate in selenium_rates}
        travelline_map = {_business_key(rate): rate for rate in travelline_rates}

        keys = sorted(set(selenium_map.keys()) | set(travelline_map.keys()))
        exact_price_matches = 0
        price_mismatches = 0
        selenium_only_rows = 0
        travelline_only_rows = 0

        with diff_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "status",
                    "date",
                    "adults_count",
                    "category_id",
                    "group_id",
                    "tariff_code",
                    "selenium_amount_minor",
                    "travelline_amount_minor",
                    "note",
                ],
            )
            writer.writeheader()
            for key in keys:
                selenium_rate = selenium_map.get(key)
                travelline_rate = travelline_map.get(key)
                note = ""
                status = "match"
                if selenium_rate is None:
                    status = "travelline_only"
                    travelline_only_rows += 1
                elif travelline_rate is None:
                    status = "selenium_only"
                    selenium_only_rows += 1
                elif selenium_rate.price.amount_minor == travelline_rate.price.amount_minor:
                    exact_price_matches += 1
                else:
                    status = "price_mismatch"
                    price_mismatches += 1
                    note = (
                        f"selenium={selenium_rate.price.amount_minor};"
                        f"travelline={travelline_rate.price.amount_minor}"
                    )

                writer.writerow(
                    {
                        "status": status,
                        "date": key[0],
                        "adults_count": key[1],
                        "category_id": key[2],
                        "group_id": key[3],
                        "tariff_code": key[4],
                        "selenium_amount_minor": "" if selenium_rate is None else selenium_rate.price.amount_minor,
                        "travelline_amount_minor": "" if travelline_rate is None else travelline_rate.price.amount_minor,
                        "note": note,
                    }
                )

            for mismatch in transform_result.category_mapping_mismatches:
                writer.writerow(
                    {
                        "status": "category_mapping_mismatch",
                        "date": "",
                        "adults_count": "",
                        "category_id": mismatch.fallback_category_id,
                        "group_id": "",
                        "tariff_code": "",
                        "selenium_amount_minor": "",
                        "travelline_amount_minor": "",
                        "note": (
                            f"room_type_code={mismatch.room_type_code};"
                            f"room_type_name={mismatch.room_type_name or ''}"
                        ),
                    }
                )

            for anomaly in transform_result.tariff_pairing_anomalies:
                writer.writerow(
                    {
                        "status": "tariff_pairing_anomaly",
                        "date": anomaly.stay_date.isoformat(),
                        "adults_count": anomaly.adults,
                        "category_id": anomaly.room_type_name or anomaly.room_type_code,
                        "group_id": "",
                        "tariff_code": "",
                        "selenium_amount_minor": "",
                        "travelline_amount_minor": "",
                        "note": (
                            f"room_type_code={anomaly.room_type_code};"
                            f"prices={list(anomaly.observed_prices)};quotes={anomaly.quotes_count};"
                            f"reason={anomaly.reason}"
                        ),
                    }
                )

        with travelline_rates_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "date",
                    "adults_count",
                    "category_id",
                    "group_id",
                    "tariff_code",
                    "travelline_amount_minor",
                    "currency",
                    "is_available",
                    "is_last_room",
                ],
            )
            writer.writeheader()
            for rate in sorted(travelline_rates, key=_business_key):
                writer.writerow(
                    {
                        "date": rate.date.isoformat(),
                        "adults_count": rate.adults_count,
                        "category_id": rate.category_id,
                        "group_id": rate.group_id or "",
                        "tariff_code": rate.tariff_code,
                        "travelline_amount_minor": rate.price.amount_minor,
                        "currency": rate.price.currency,
                        "is_available": rate.is_available,
                        "is_last_room": rate.is_last_room,
                    }
                )

        summary_payload = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "adults_counts": list(adults_counts),
            "selenium_total_rows": len(selenium_rates),
            "travelline_total_rows": len(travelline_rates),
            "selenium_only_rows": selenium_only_rows,
            "travelline_only_rows": travelline_only_rows,
            "exact_price_matches": exact_price_matches,
            "price_mismatches": price_mismatches,
            "unmapped_categories": len(transform_result.category_mapping_mismatches),
            "tariff_pairing_anomalies": len(transform_result.tariff_pairing_anomalies),
            "duplicates_removed": len(transform_result.duplicate_keys),
            "summary_path": str(summary_path),
            "diff_path": str(diff_path),
            "travelline_rates_path": str(travelline_rates_path),
        }
        summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return TravellineCompareSummary(
            date_from=date_from,
            date_to=date_to,
            adults_counts=adults_counts,
            selenium_total_rows=len(selenium_rates),
            travelline_total_rows=len(travelline_rates),
            selenium_only_rows=selenium_only_rows,
            travelline_only_rows=travelline_only_rows,
            exact_price_matches=exact_price_matches,
            price_mismatches=price_mismatches,
            unmapped_categories=len(transform_result.category_mapping_mismatches),
            tariff_pairing_anomalies=len(transform_result.tariff_pairing_anomalies),
            duplicates_removed=len(transform_result.duplicate_keys),
            summary_path=str(summary_path),
            diff_path=str(diff_path),
            travelline_rates_path=str(travelline_rates_path),
        )


def _business_key(rate: DailyRate) -> tuple[str, int, str, str, str]:
    return (
        rate.date.isoformat(),
        rate.adults_count,
        rate.category_id,
        rate.group_id or "",
        rate.tariff_code,
    )
