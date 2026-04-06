from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.infrastructure.parsers.travelline_rates_parser_runner import (
    TravellinePublishRunError,
    TravellineRatesParserRunner,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeatureFlaggedRatesRunner:
    selenium_runner: SeleniumRatesParserRunner
    travelline_runner: TravellineRatesParserRunner | None = None
    use_travelline_rates_source: bool = False
    travelline_compare_only: bool = False
    travelline_enable_publish: bool = False
    travelline_fallback_to_selenium: bool = True

    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int:
        logger.info(
            "rates_source_rollout use_travelline_rates_source=%s travelline_publish_enabled=%s "
            "travelline_compare_only=%s travelline_fallback_to_selenium=%s",
            self.use_travelline_rates_source,
            self.travelline_enable_publish,
            self.travelline_compare_only,
            self.travelline_fallback_to_selenium,
        )

        use_travelline_publish = (
            self.use_travelline_rates_source
            and self.travelline_enable_publish
            and self.travelline_runner is not None
        )
        if use_travelline_publish:
            logger.info("rates_source_selected=travelline")
            try:
                return self.travelline_runner.run(
                    start_date=start_date,
                    days_to_collect=days_to_collect,
                    adults_counts=adults_counts,
                )
            except TravellinePublishRunError as exc:
                logger.exception("travelline_publish_failed")
                if not self.travelline_fallback_to_selenium:
                    logger.warning("travelline_fallback_triggered=false reason=disabled")
                    raise
                self.travelline_runner.mark_fallback_used(report=exc.report)
                logger.warning(
                    "travelline_fallback_triggered=true source=selenium reason=%s",
                    ";".join(exc.report.validation_failure_reasons),
                )
                rows = self.selenium_runner.run(
                    start_date=start_date,
                    days_to_collect=days_to_collect,
                    adults_counts=adults_counts,
                )
                logger.info("selenium_publish_rows=%s", rows)
                return rows
            except Exception:
                logger.exception("travelline_publish_failed")
                if not self.travelline_fallback_to_selenium:
                    logger.warning("travelline_fallback_triggered=false reason=disabled")
                    raise
                logger.warning("travelline_fallback_triggered=true source=selenium")
                rows = self.selenium_runner.run(
                    start_date=start_date,
                    days_to_collect=days_to_collect,
                    adults_counts=adults_counts,
                )
                logger.info("selenium_publish_rows=%s", rows)
                return rows

        logger.info("rates_source_selected=selenium")
        rows = self.selenium_runner.run(
            start_date=start_date,
            days_to_collect=days_to_collect,
            adults_counts=adults_counts,
        )
        logger.info("selenium_publish_rows=%s", rows)
        if self._should_run_compare_only():
            self._run_compare_only(
                start_date=start_date,
                days_to_collect=days_to_collect,
                adults_counts=adults_counts,
            )
        return rows

    def _should_run_compare_only(self) -> bool:
        return self.travelline_compare_only and self.travelline_runner is not None

    def _run_compare_only(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> None:
        date_to = start_date + timedelta(days=days_to_collect - 1)
        try:
            result = self.travelline_runner.run_compare_only(
                date_from=start_date,
                date_to=date_to,
                adults_counts=adults_counts,
            )
            logger.info(
                "travelline_compare_only_complete travelline_total_rows=%s price_mismatches=%s "
                "tariff_pairing_anomalies=%s",
                result.summary.travelline_total_rows,
                result.summary.price_mismatches,
                result.summary.tariff_pairing_anomalies,
            )
        except Exception:
            logger.exception("travelline_compare_only_failed")
