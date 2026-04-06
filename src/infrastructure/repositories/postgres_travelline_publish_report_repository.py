from __future__ import annotations

import os

from sqlalchemy import BOOLEAN, DATE, INTEGER, TEXT, TIMESTAMP, Column, ForeignKey, MetaData, Table, create_engine, select, text

from src.application.dto.travelline_publish_report import (
    TravellinePublishAdultsSummary,
    TravellinePublishDateStat,
    TravellinePublishRunReport,
)
from src.application.ports.travelline_publish_report_repository import TravellinePublishReportRepository


metadata = MetaData()

travelline_publish_runs_table = Table(
    "travelline_publish_runs",
    metadata,
    Column("run_id", TEXT, primary_key=True),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("completed_at", TIMESTAMP, nullable=False),
    Column("mode", TEXT, nullable=False),
    Column("validation_status", TEXT, nullable=False),
    Column("validation_failure_reasons", TEXT, nullable=True),
    Column("fallback_used", BOOLEAN, nullable=False),
    Column("expected_dates_count", INTEGER, nullable=False),
    Column("actual_dates_count", INTEGER, nullable=False),
    Column("dates_with_no_categories_count", INTEGER, nullable=False),
    Column("total_final_rows_count", INTEGER, nullable=False),
    Column("tariff_pairing_anomalies_count", INTEGER, nullable=False),
    Column("unmapped_categories_count", INTEGER, nullable=False),
)

travelline_publish_run_adults_table = Table(
    "travelline_publish_run_adults",
    metadata,
    Column("run_id", TEXT, ForeignKey("travelline_publish_runs.run_id", ondelete="CASCADE"), nullable=False),
    Column("adults_count", INTEGER, nullable=False),
    Column("expected_requests_count", INTEGER, nullable=False),
    Column("attempted_count", INTEGER, nullable=False),
    Column("success_count", INTEGER, nullable=False),
    Column("fail_count", INTEGER, nullable=False),
    Column("collected_final_rows_count", INTEGER, nullable=False),
    Column("status", TEXT, nullable=False),
)

travelline_publish_run_empty_dates_table = Table(
    "travelline_publish_run_empty_dates",
    metadata,
    Column("run_id", TEXT, ForeignKey("travelline_publish_runs.run_id", ondelete="CASCADE"), nullable=False),
    Column("stay_date", DATE, nullable=False),
)

travelline_publish_run_date_rows_table = Table(
    "travelline_publish_run_date_rows",
    metadata,
    Column("run_id", TEXT, ForeignKey("travelline_publish_runs.run_id", ondelete="CASCADE"), nullable=False),
    Column("stay_date", DATE, nullable=False),
    Column("rows_count", INTEGER, nullable=False),
)


class PostgresTravellinePublishReportRepository(TravellinePublishReportRepository):
    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL")
        if not url:
            raise ValueError("DATABASE_URL is required for PostgresTravellinePublishReportRepository")
        self._engine = create_engine(url, future=True)
        self._init_schema()

    def _init_schema(self) -> None:
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_tl_publish_runs_completed_at "
                    "ON travelline_publish_runs(completed_at DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_tl_publish_run_adults_run "
                    "ON travelline_publish_run_adults(run_id, adults_count)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_tl_publish_empty_dates_run "
                    "ON travelline_publish_run_empty_dates(run_id, stay_date)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_tl_publish_date_rows_run "
                    "ON travelline_publish_run_date_rows(run_id, stay_date)"
                )
            )

    def save_run_report(self, *, report: TravellinePublishRunReport) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM travelline_publish_run_adults WHERE run_id = :run_id"),
                {"run_id": report.run_id},
            )
            conn.execute(
                text("DELETE FROM travelline_publish_run_empty_dates WHERE run_id = :run_id"),
                {"run_id": report.run_id},
            )
            conn.execute(
                text("DELETE FROM travelline_publish_run_date_rows WHERE run_id = :run_id"),
                {"run_id": report.run_id},
            )
            conn.execute(
                text("DELETE FROM travelline_publish_runs WHERE run_id = :run_id"),
                {"run_id": report.run_id},
            )
            conn.execute(
                travelline_publish_runs_table.insert(),
                {
                    "run_id": report.run_id,
                    "created_at": report.created_at,
                    "completed_at": report.completed_at,
                    "mode": report.mode,
                    "validation_status": report.validation_status,
                    "validation_failure_reasons": "\n".join(report.validation_failure_reasons),
                    "fallback_used": report.fallback_used,
                    "expected_dates_count": report.expected_dates_count,
                    "actual_dates_count": report.actual_dates_count,
                    "dates_with_no_categories_count": report.dates_with_no_categories_count,
                    "total_final_rows_count": report.total_final_rows_count,
                    "tariff_pairing_anomalies_count": report.tariff_pairing_anomalies_count,
                    "unmapped_categories_count": report.unmapped_categories_count,
                },
            )
            if report.adults_summaries:
                conn.execute(
                    travelline_publish_run_adults_table.insert(),
                    [
                        {
                            "run_id": report.run_id,
                            "adults_count": item.adults_count,
                            "expected_requests_count": item.expected_requests_count,
                            "attempted_count": item.attempted_count,
                            "success_count": item.success_count,
                            "fail_count": item.fail_count,
                            "collected_final_rows_count": item.collected_final_rows_count,
                            "status": item.status,
                        }
                        for item in report.adults_summaries
                    ],
                )
            if report.empty_dates:
                conn.execute(
                    travelline_publish_run_empty_dates_table.insert(),
                    [
                        {
                            "run_id": report.run_id,
                            "stay_date": stay_date,
                        }
                        for stay_date in report.empty_dates
                    ],
                )
            if report.per_date_rows:
                conn.execute(
                    travelline_publish_run_date_rows_table.insert(),
                    [
                        {
                            "run_id": report.run_id,
                            "stay_date": item.stay_date,
                            "rows_count": item.rows_count,
                        }
                        for item in report.per_date_rows
                    ],
                )

    def mark_fallback_used(self, *, run_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE travelline_publish_runs "
                    "SET fallback_used = TRUE "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            )

    def get_latest_run_report(self) -> TravellinePublishRunReport | None:
        stmt = (
            select(travelline_publish_runs_table)
            .order_by(travelline_publish_runs_table.c.completed_at.desc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
            if row is None:
                return None
            run_id = str(row["run_id"])
            adults_rows = conn.execute(
                select(travelline_publish_run_adults_table)
                .where(travelline_publish_run_adults_table.c.run_id == run_id)
                .order_by(travelline_publish_run_adults_table.c.adults_count.asc())
            ).mappings()
            empty_dates_rows = conn.execute(
                select(travelline_publish_run_empty_dates_table)
                .where(travelline_publish_run_empty_dates_table.c.run_id == run_id)
                .order_by(travelline_publish_run_empty_dates_table.c.stay_date.asc())
            ).mappings()
            date_rows = conn.execute(
                select(travelline_publish_run_date_rows_table)
                .where(travelline_publish_run_date_rows_table.c.run_id == run_id)
                .order_by(travelline_publish_run_date_rows_table.c.stay_date.asc())
            ).mappings()
            return TravellinePublishRunReport(
                run_id=run_id,
                created_at=row["created_at"],
                completed_at=row["completed_at"],
                mode=row["mode"],
                validation_status=row["validation_status"],
                validation_failure_reasons=tuple(
                    item for item in str(row["validation_failure_reasons"] or "").splitlines() if item.strip()
                ),
                fallback_used=bool(row["fallback_used"]),
                expected_dates_count=int(row["expected_dates_count"]),
                actual_dates_count=int(row["actual_dates_count"]),
                dates_with_no_categories_count=int(row["dates_with_no_categories_count"]),
                total_final_rows_count=int(row["total_final_rows_count"]),
                tariff_pairing_anomalies_count=int(row["tariff_pairing_anomalies_count"]),
                unmapped_categories_count=int(row["unmapped_categories_count"]),
                adults_summaries=tuple(
                    TravellinePublishAdultsSummary(
                        adults_count=int(item["adults_count"]),
                        expected_requests_count=int(item["expected_requests_count"]),
                        attempted_count=int(item["attempted_count"]),
                        success_count=int(item["success_count"]),
                        fail_count=int(item["fail_count"]),
                        collected_final_rows_count=int(item["collected_final_rows_count"]),
                        status=str(item["status"]),
                    )
                    for item in adults_rows
                ),
                empty_dates=tuple(item["stay_date"] for item in empty_dates_rows),
                per_date_rows=tuple(
                    TravellinePublishDateStat(
                        stay_date=item["stay_date"],
                        rows_count=int(item["rows_count"]),
                    )
                    for item in date_rows
                ),
            )
