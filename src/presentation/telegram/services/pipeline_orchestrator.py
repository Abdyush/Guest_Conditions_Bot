from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta

from telegram import Bot
from telegram.error import TelegramError

from src.infrastructure.parsers.selenium_offers_parser_runner import SeleniumOffersParserRunner
from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.presentation.telegram.keyboards.main_menu import build_notified_categories_inline_keyboard
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
            return RunAttempt(False, f"busy:{self._active_run_name}")
        async with self._run_lock:
            self._active_run_name = "nightly_pipeline"
            try:
                today = date.today()
                end_date = today + timedelta(days=29)
                logger.info("pipeline_start trigger=%s date_from=%s date_to=%s", trigger, today.isoformat(), end_date.isoformat())

                logger.info("parser_categories_start trigger=%s", trigger)
                rates_count = await asyncio.to_thread(
                    self._rates_runner.run,
                    start_date=today,
                    days_to_collect=30,
                    adults_counts=(1, 2, 3, 4, 5, 6),
                )
                logger.info("parser_categories_finish trigger=%s rows=%s", trigger, rates_count)

                logger.info("parser_offers_start trigger=%s", trigger)
                offers_count = await asyncio.to_thread(
                    self._offers_runner.run,
                    booking_date=today,
                )
                logger.info("parser_offers_finish trigger=%s rows=%s", trigger, offers_count)

                logger.info("recalculate_start trigger=%s", trigger)
                run_id = await asyncio.to_thread(
                    self._adapter.recalculate_matches,
                    date_from=today,
                    date_to=end_date,
                    booking_date=today,
                    trigger=f"pipeline:{trigger}",
                )
                logger.info("recalculate_finish trigger=%s run_id=%s", trigger, run_id)

                logger.info("notifications_start trigger=%s run_id=%s", trigger, run_id)
                notified = await self._notify_guests(bot=bot)
                logger.info("notifications_finish trigger=%s run_id=%s notified=%s", trigger, run_id, notified)
                logger.info("pipeline_finish trigger=%s run_id=%s", trigger, run_id)
                return RunAttempt(True, f"ok:{run_id}")
            except Exception:
                logger.exception("pipeline_error trigger=%s", trigger)
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_categories_parser(self, *, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
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
                return RunAttempt(True, f"parsed_rates:{rows}")
            except Exception:
                logger.exception("parser_categories_error trigger=%s", trigger)
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def run_offers_parser(self, *, trigger: str) -> RunAttempt:
        if self._run_lock.locked():
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
                return RunAttempt(True, f"parsed_offers:{rows}")
            except Exception:
                logger.exception("parser_offers_error trigger=%s", trigger)
                return RunAttempt(False, "error")
            finally:
                self._active_run_name = "idle"

    async def _notify_guests(self, *, bot: Bot | None) -> int:
        if bot is None:
            logger.warning("notifications_skip reason=no_bot_instance")
            return 0
        targets = await asyncio.to_thread(self._adapter.build_notification_targets)
        sent_messages = 0
        for target in targets:
            if target.category_names:
                text = f"Дорогой {target.guest_name}, по Вашим условиям подошли следующие категории:"
                markup = build_notified_categories_inline_keyboard(category_names=target.category_names)
            else:
                text = f"Дорогой {target.guest_name}, по Вашим условиям сейчас нет подходящих категорий."
                markup = None

            for telegram_user_id in target.telegram_user_ids:
                try:
                    await bot.send_message(chat_id=telegram_user_id, text=text, reply_markup=markup)
                    sent_messages += 1
                except TelegramError:
                    logger.exception(
                        "notification_send_error guest_id=%s telegram_user_id=%s",
                        target.guest_id,
                        telegram_user_id,
                    )
        return sent_messages
