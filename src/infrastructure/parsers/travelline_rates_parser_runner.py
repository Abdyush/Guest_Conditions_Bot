from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.application.ports.rates_repository import RatesRepository
from src.domain.entities.rate import DailyRate
from src.infrastructure.sources.travelline_rates_source import TravellineRatesSource
from src.infrastructure.travelline.models import TravellineRatesTransformResult


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


@dataclass(frozen=True, slots=True)
class TravellineCompareRunResult:
    summary: TravellineCompareSummary
    transform_result: TravellineRatesTransformResult


@dataclass(frozen=True, slots=True)
class TravellineRatesParserRunner:
    source: TravellineRatesSource
    rates_repo: RatesRepository
    artifacts_dir: Path = Path("artifacts") / "compare"

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
        )


def _business_key(rate: DailyRate) -> tuple[str, int, str, str, str]:
    return (
        rate.date.isoformat(),
        rate.adults_count,
        rate.category_id,
        rate.group_id or "",
        rate.tariff_code,
    )
