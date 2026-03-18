from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from telegram import Bot
from telegram.error import TelegramError

from src.infrastructure.parsers.selenium_offers_parser_runner import SeleniumOffersParserRunner
from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.presentation.telegram.keyboards.notification_offers import (
    build_notification_groups_inline_keyboard,
    build_notification_scenario_keyboard,
)
from src.presentation.telegram.presenters.available_presenter import build_available_groups
from src.presentation.telegram.presenters.notification_offers_presenter import (
    render_notification_groups_prompt,
    render_notification_intro,
)
from src.presentation.telegram.services.use_cases_adapter import TelegramUseCasesAdapter


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunAttempt:
    started: bool
    message: str


class PipelineOrchestrator:
    def __init__(
        self,
        *,
        adapter: TelegramUseCasesAdapter,
        rates_runner: SeleniumRatesParserRunner,
        offers_runner: SeleniumOffersParserRunner,
    ):
        self._adapter = adapter
        self._rates_runner = rates_runner
        self._offers_runner = offers_runner
        self._run_lock = asyncio.Lock()
        self._active_run_name = "idle"

    async def run_daily_pipeline(self, *, bot: Bot | None, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
            self._adapter.log_admin_event(
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
                end_date = today + timedelta(days=29)
                logger.info("pipeline_start trigger=%s date_from=%s date_to=%s", trigger, today.isoformat(), end_date.isoformat())

                try:
                    logger.info("parser_categories_start trigger=%s", trigger)
                    rates_count = await asyncio.to_thread(
                        self._rates_runner.run,
                        start_date=today,
                        days_to_collect=30,
                        adults_counts=(1, 2, 3, 4, 5, 6),
                    )
                    logger.info("parser_categories_finish trigger=%s rows=%s", trigger, rates_count)
                    self._adapter.log_admin_event(
                        event_type="parser_rates_run",
                        status="success",
                        trigger=trigger,
                        message=f"rows={rates_count}",
                    )
                except Exception:
                    self._adapter.log_admin_event(
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
                    self._adapter.log_admin_event(
                        event_type="parser_offers_run",
                        status="success",
                        trigger=trigger,
                        message=f"rows={offers_count}",
                    )
                except Exception:
                    self._adapter.log_admin_event(
                        event_type="parser_offers_run",
                        status="error",
                        trigger=trigger,
                        message="error",
                    )
                    raise

                try:
                    logger.info("recalculate_start trigger=%s", trigger)
                    run_id = await asyncio.to_thread(
                        self._adapter.recalculate_matches,
                        date_from=today,
                        date_to=end_date,
                        booking_date=today,
                        trigger=f"pipeline:{trigger}",
                    )
                    logger.info("recalculate_finish trigger=%s run_id=%s", trigger, run_id)
                    self._adapter.log_admin_event(
                        event_type="recalculation_run",
                        status="success",
                        trigger=trigger,
                        message=f"run_id={run_id}",
                    )
                except Exception:
                    self._adapter.log_admin_event(
                        event_type="recalculation_run",
                        status="error",
                        trigger=trigger,
                        message="error",
                    )
                    raise

                logger.info("notifications_start trigger=%s run_id=%s", trigger, run_id)
                notified = await self._notify_guests(bot=bot, run_id=run_id)
                logger.info("notifications_finish trigger=%s run_id=%s notified=%s", trigger, run_id, notified)
                logger.info("pipeline_finish trigger=%s run_id=%s", trigger, run_id)
                self._adapter.log_admin_event(
                    event_type="pipeline_run",
                    status="success",
                    trigger=trigger,
                    message=f"run_id={run_id};notified={notified}",
                )
                return RunAttempt(True, f"ok:{run_id}")
            except Exception:
                logger.exception("pipeline_error trigger=%s", trigger)
                self._adapter.log_admin_event(
                    event_type="pipeline_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_categories_parser(self, *, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
            self._adapter.log_admin_event(
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
                    days_to_collect=30,
                    adults_counts=(1, 2, 3, 4, 5, 6),
                )
                logger.info("parser_categories_finish trigger=%s rows=%s", trigger, rows)
                self._adapter.log_admin_event(
                    event_type="parser_rates_run",
                    status="success",
                    trigger=trigger,
                    message=f"rows={rows}",
                )
                return RunAttempt(True, f"parsed_rates:{rows}")
            except Exception:
                logger.exception("parser_categories_error trigger=%s", trigger)
                self._adapter.log_admin_event(
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
            self._adapter.log_admin_event(
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
                self._adapter.log_admin_event(
                    event_type="parser_offers_run",
                    status="success",
                    trigger=trigger,
                    message=f"rows={rows}",
                )
                return RunAttempt(True, f"parsed_offers:{rows}")
            except Exception:
                logger.exception("parser_offers_error trigger=%s", trigger)
                self._adapter.log_admin_event(
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
            self._adapter.log_admin_event(
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
                end_date = today + timedelta(days=29)
                run_id = await asyncio.to_thread(
                    self._adapter.recalculate_matches,
                    date_from=today,
                    date_to=end_date,
                    booking_date=today,
                    trigger=trigger,
                )
                self._adapter.log_admin_event(
                    event_type="recalculation_run",
                    status="success",
                    trigger=trigger,
                    message=f"run_id={run_id}",
                )
                return RunAttempt(True, f"ok:{run_id}")
            except Exception:
                logger.exception("recalculation_error trigger=%s", trigger)
                self._adapter.log_admin_event(
                    event_type="recalculation_run",
                    status="error",
                    trigger=trigger,
                    message="error",
                )
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"


    async def _notify_guests(self, *, bot: Bot | None, run_id: str) -> int:
        if bot is None:
            logger.warning("notifications_skip reason=no_bot_instance")
            return 0
        targets = await asyncio.to_thread(self._adapter.prepare_new_notification_batches, run_id=run_id)
        sent_recipients = 0
        for target in targets:
            sent_for_guest = False
            group_names = [group.label for group in build_available_groups(category_groups=target.category_groups)]
            intro_text = render_notification_intro(guest_name=target.guest_name)
            groups_text = render_notification_groups_prompt()
            markup = build_notification_groups_inline_keyboard(run_id=target.run_id, group_names=group_names)

            for telegram_user_id in target.telegram_user_ids:
                try:
                    await bot.send_message(
                        chat_id=telegram_user_id,
                        text=intro_text,
                        reply_markup=build_notification_scenario_keyboard(),
                    )
                    await bot.send_message(chat_id=telegram_user_id, text=groups_text, reply_markup=markup)
                    sent_for_guest = True
                    sent_recipients += 1
                except TelegramError:
                    logger.exception(
                        "notification_send_error guest_id=%s telegram_user_id=%s",
                        target.guest_id,
                        telegram_user_id,
                    )
            if sent_for_guest:
                await asyncio.to_thread(
                    self._adapter.mark_notification_rows_sent,
                    run_id=target.run_id,
                    rows=target.rows,
                )
        return sent_recipients
