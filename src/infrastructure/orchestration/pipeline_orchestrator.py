from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol, Sequence

from src.application.dto.guest_notification_batch import GuestNotificationBatch
from src.application.dto.matched_date_record import MatchedDateRecord
from src.application.ports.matches_run_repository import MatchesRunRepository
from src.infrastructure.parsers.selenium_offers_parser_runner import SeleniumOffersParserRunner


logger = logging.getLogger(__name__)


class AdminEventLogger(Protocol):
    def log_admin_event(
        self,
        *,
        event_type: str,
        status: str,
        trigger: str | None = None,
        message: str | None = None,
        user_id: int | None = None,
    ) -> None: ...


class SystemRecalculationPort(Protocol):
    def recalculate_matches(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        booking_date: date | None = None,
        trigger: str = "direct",
    ) -> str: ...


class NotificationsPort(Protocol):
    def prepare_new_notification_batches(self, *, run_id: str, as_of_date: date | None = None) -> list[GuestNotificationBatch]: ...

    def mark_notification_rows_sent(self, *, run_id: str, rows: list[MatchedDateRecord]) -> None: ...


@dataclass(frozen=True, slots=True)
class NotificationDeliveryResult:
    sent_recipients: int
    delivered_targets: tuple[GuestNotificationBatch, ...]


class NotificationDelivery(Protocol):
    async def deliver_batches(
        self,
        *,
        bot: object | None,
        targets: Sequence[GuestNotificationBatch],
    ) -> NotificationDeliveryResult: ...


class RatesPipelineRunner(Protocol):
    def run(self, *, start_date: date, days_to_collect: int, adults_counts: tuple[int, ...]) -> int: ...


@dataclass(frozen=True, slots=True)
class RunAttempt:
    started: bool
    message: str


class PipelineOrchestrator:
    def __init__(
        self,
        *,
        admin: AdminEventLogger,
        system: SystemRecalculationPort,
        notifications: NotificationsPort,
        latest_runs: MatchesRunRepository,
        notification_delivery: NotificationDelivery,
        rates_runner: RatesPipelineRunner,
        offers_runner: SeleniumOffersParserRunner,
        matches_lookahead_days: int = 90,
    ):
        self._admin = admin
        self._system = system
        self._notifications = notifications
        self._latest_runs = latest_runs
        self._notification_delivery = notification_delivery
        self._rates_runner = rates_runner
        self._offers_runner = offers_runner
        self._matches_lookahead_days = matches_lookahead_days
        self._run_lock = asyncio.Lock()
        self._active_run_name = "idle"

    @property
    def active_run_name(self) -> str:
        return self._active_run_name

    def is_busy(self) -> bool:
        return self._run_lock.locked()

    async def run_daily_pipeline(self, *, bot: object | None, trigger: str, with_notifications: bool = True) -> RunAttempt:
        if self._run_lock.locked():
            self._admin.log_admin_event(
                event_type="pipeline_run",
                status="busy",
                trigger=trigger,
                message=f"busy:{self._active_run_name}",
            )
            return RunAttempt(False, f"busy:{self._active_run_name}")
        async with self._run_lock:
            self._active_run_name = "nightly_pipeline"
            try:
                today = date.today()
                end_date = today + timedelta(days=self._matches_lookahead_days - 1)
                logger.info("pipeline_start trigger=%s date_from=%s date_to=%s", trigger, today.isoformat(), end_date.isoformat())

                try:
                    logger.info("parser_categories_start trigger=%s", trigger)
                    rates_count = await asyncio.to_thread(
                        self._rates_runner.run,
                        start_date=today,
                        days_to_collect=self._matches_lookahead_days,
                        adults_counts=(1, 2, 3, 4, 5, 6),
                    )
                    logger.info("parser_categories_finish trigger=%s rows=%s", trigger, rates_count)
                    self._admin.log_admin_event(
                        event_type="parser_rates_run",
                        status="success",
                        trigger=trigger,
                        message=f"rows={rates_count}",
                    )
                except Exception:
                    self._admin.log_admin_event(
                        event_type="parser_rates_run",
                        status="error",
                        trigger=trigger,
                        message="error",
                    )
                    raise

                try:
                    logger.info("parser_offers_start trigger=%s", trigger)
                    offers_count = await asyncio.to_thread(
                        self._offers_runner.run,
                        booking_date=today,
                    )
                    logger.info("parser_offers_finish trigger=%s rows=%s", trigger, offers_count)
                    self._admin.log_admin_event(
                        event_type="parser_offers_run",
                        status="success",
                        trigger=trigger,
                        message=f"rows={offers_count}",
                    )
                except Exception:
                    self._admin.log_admin_event(
                        event_type="parser_offers_run",
                        status="error",
                        trigger=trigger,
                        message="error",
                    )
                    raise

                try:
                    logger.info("recalculate_start trigger=%s", trigger)
                    run_id = await asyncio.to_thread(
                        self._system.recalculate_matches,
                        date_from=today,
                        date_to=end_date,
                        booking_date=today,
                        trigger=f"pipeline:{trigger}",
                    )
                    logger.info("recalculate_finish trigger=%s run_id=%s", trigger, run_id)
                    self._admin.log_admin_event(
                        event_type="recalculation_run",
                        status="success",
                        trigger=trigger,
                        message=f"run_id={run_id}",
                    )
                except Exception:
                    self._admin.log_admin_event(
                        event_type="recalculation_run",
                        status="error",
                        trigger=trigger,
                        message="error",
                    )
                    raise

                notified = 0
                if with_notifications:
                    logger.info("notifications_start trigger=%s run_id=%s", trigger, run_id)
                    notified = await self._notify_guests(bot=bot, run_id=run_id)
                    logger.info("notifications_finish trigger=%s run_id=%s notified=%s", trigger, run_id, notified)
                logger.info("pipeline_finish trigger=%s run_id=%s", trigger, run_id)
                self._admin.log_admin_event(
                    event_type="pipeline_run",
                    status="success",
                    trigger=trigger,
                    message=f"run_id={run_id};notified={notified}",
                )
                return RunAttempt(True, f"ok:{run_id}")
            except Exception:
                logger.exception("pipeline_error trigger=%s", trigger)
                self._admin.log_admin_event(
                    event_type="pipeline_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_notifications_only(self, *, bot: object | None, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
            self._admin.log_admin_event(
                event_type="notifications_run",
                status="busy",
                trigger=trigger,
                message=f"busy:{self._active_run_name}",
            )
            return RunAttempt(False, f"busy:{self._active_run_name}")
        async with self._run_lock:
            self._active_run_name = "notifications_only"
            try:
                run_id = await asyncio.to_thread(self._latest_runs.get_latest_run_id)
                if not run_id:
                    self._admin.log_admin_event(
                        event_type="notifications_run",
                        status="success",
                        trigger=trigger,
                        message="run_id=none;notified=0",
                    )
                    return RunAttempt(False, "no_run")

                logger.info("notifications_start trigger=%s run_id=%s", trigger, run_id)
                notified = await self._notify_guests(bot=bot, run_id=run_id)
                logger.info("notifications_finish trigger=%s run_id=%s notified=%s", trigger, run_id, notified)
                self._admin.log_admin_event(
                    event_type="notifications_run",
                    status="success",
                    trigger=trigger,
                    message=f"run_id={run_id};notified={notified}",
                )
                return RunAttempt(True, f"ok:{run_id}")
            except Exception:
                logger.exception("notifications_only_error trigger=%s", trigger)
                self._admin.log_admin_event(
                    event_type="notifications_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_categories_parser(self, *, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
            self._admin.log_admin_event(
                event_type="parser_rates_run",
                status="busy",
                trigger=trigger,
                message=f"busy:{self._active_run_name}",
            )
            return RunAttempt(False, f"busy:{self._active_run_name}")
        async with self._run_lock:
            self._active_run_name = "categories_parser"
            try:
                today = date.today()
                logger.info("manual_start trigger=%s process=parser_categories", trigger)
                logger.info("parser_categories_start trigger=%s", trigger)
                rows = await asyncio.to_thread(
                    self._rates_runner.run,
                    start_date=today,
                    days_to_collect=self._matches_lookahead_days,
                    adults_counts=(1, 2, 3, 4, 5, 6),
                )
                logger.info("parser_categories_finish trigger=%s rows=%s", trigger, rows)
                self._admin.log_admin_event(
                    event_type="parser_rates_run",
                    status="success",
                    trigger=trigger,
                    message=f"rows={rows}",
                )
                return RunAttempt(True, f"parsed_rates:{rows}")
            except Exception:
                logger.exception("parser_categories_error trigger=%s", trigger)
                self._admin.log_admin_event(
                    event_type="parser_rates_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_offers_parser(self, *, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
            self._admin.log_admin_event(
                event_type="parser_offers_run",
                status="busy",
                trigger=trigger,
                message=f"busy:{self._active_run_name}",
            )
            return RunAttempt(False, f"busy:{self._active_run_name}")
        async with self._run_lock:
            self._active_run_name = "offers_parser"
            try:
                today = date.today()
                logger.info("manual_start trigger=%s process=parser_offers", trigger)
                logger.info("parser_offers_start trigger=%s", trigger)
                rows = await asyncio.to_thread(
                    self._offers_runner.run,
                    booking_date=today,
                )
                logger.info("parser_offers_finish trigger=%s rows=%s", trigger, rows)
                self._admin.log_admin_event(
                    event_type="parser_offers_run",
                    status="success",
                    trigger=trigger,
                    message=f"rows={rows}",
                )
                return RunAttempt(True, f"parsed_offers:{rows}")
            except Exception:
                logger.exception("parser_offers_error trigger=%s", trigger)
                self._admin.log_admin_event(
                    event_type="parser_offers_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_recalculation(self, *, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
            self._admin.log_admin_event(
                event_type="recalculation_run",
                status="busy",
                trigger=trigger,
                message=f"busy:{self._active_run_name}",
            )
            return RunAttempt(False, f"busy:{self._active_run_name}")
        async with self._run_lock:
            self._active_run_name = "recalculation"
            try:
                today = date.today()
                end_date = today + timedelta(days=self._matches_lookahead_days - 1)
                run_id = await asyncio.to_thread(
                    self._system.recalculate_matches,
                    date_from=today,
                    date_to=end_date,
                    booking_date=today,
                    trigger=trigger,
                )
                self._admin.log_admin_event(
                    event_type="recalculation_run",
                    status="success",
                    trigger=trigger,
                    message=f"run_id={run_id}",
                )
                return RunAttempt(True, f"ok:{run_id}")
            except Exception:
                logger.exception("recalculation_error trigger=%s", trigger)
                self._admin.log_admin_event(
                    event_type="recalculation_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def _notify_guests(self, *, bot: object | None, run_id: str) -> int:
        targets = await asyncio.to_thread(self._notifications.prepare_new_notification_batches, run_id=run_id)
        delivery_result = await self._notification_delivery.deliver_batches(bot=bot, targets=targets)
        for target in delivery_result.delivered_targets:
            await asyncio.to_thread(
                self._notifications.mark_notification_rows_sent,
                run_id=target.run_id,
                rows=target.rows,
            )
        return delivery_result.sent_recipients
