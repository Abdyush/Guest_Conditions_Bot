from __future__ import annotations

import asyncio
import logging
import os
import warnings
from datetime import datetime, time as dt_time
from datetime import timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from aiogram.fsm.storage.redis import RedisStorage
from telegram.error import Forbidden
from telegram.warnings import PTBUserWarning
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.infrastructure.parsers.selenium_offers_parser_runner import SeleniumOffersParserRunner
from src.infrastructure.parsers.selenium_rates_parser_runner import SeleniumRatesParserRunner
from src.presentation.telegram.handlers.bot_handlers import TelegramBotHandlers
from src.presentation.telegram.services.pipeline_orchestrator import PipelineOrchestrator
from src.presentation.telegram.services.use_cases_adapter import TelegramUseCasesAdapter
from src.presentation.telegram.state.session_store import InMemorySessionStore


async def _run_daily_fallback(
    *,
    application: Application,
    bot_tz,
    pipeline: PipelineOrchestrator,
) -> None:
    logger = logging.getLogger(__name__)
    while True:
        now = datetime.now(bot_tz)
        target = datetime.combine(now.date(), dt_time(hour=3, minute=0), tzinfo=bot_tz)
        if now >= target:
            target = target + timedelta(days=1)
        sleep_seconds = max(1.0, (target - now).total_seconds())
        await asyncio.sleep(sleep_seconds)
        attempt = await pipeline.run_daily_pipeline(bot=application.bot, trigger="scheduled_fallback")
        if not attempt.started:
            logger.warning("scheduled_fallback_skip reason=%s", attempt.message)


async def _flush_sessions_loop(*, sessions: InMemorySessionStore) -> None:
    while True:
        await asyncio.sleep(2.0)
        await sessions.flush_all()


def build_bot_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    root = Path(__file__).resolve().parents[3]
    rules_csv_path = str(root / "data" / "category_rules.csv")
    headless = os.getenv("SELENIUM_VISIBLE", "").strip().lower() not in {"1", "true", "yes"}
    wait_seconds = int(os.getenv("SELENIUM_WAIT_SECONDS", "20"))
    timezone_name = os.getenv("BOT_TIMEZONE", "Europe/Moscow")
    try:
        bot_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logging.getLogger(__name__).warning(
            "timezone_not_found key=%s fallback=UTC+03:00 install=tzdata",
            timezone_name,
        )
        bot_tz = timezone(timedelta(hours=3))

    adapter = TelegramUseCasesAdapter()
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        raise ValueError("REDIS_URL is required for aiogram Redis FSM storage")
    redis_storage = RedisStorage.from_url(redis_url)
    sessions = InMemorySessionStore(storage=redis_storage)
    rates_runner = SeleniumRatesParserRunner(
        category_rules_csv_path=rules_csv_path,
        headless=headless,
        wait_seconds=wait_seconds,
    )
    offers_runner = SeleniumOffersParserRunner(
        category_rules_csv_path=rules_csv_path,
        headless=headless,
        wait_seconds=wait_seconds,
        fail_fast=False,
    )
    pipeline = PipelineOrchestrator(
        adapter=adapter,
        rates_runner=rates_runner,
        offers_runner=offers_runner,
    )
    handlers = TelegramBotHandlers(adapter=adapter, sessions=sessions, pipeline=pipeline)

    app = Application.builder().token(token).build()

    async def on_error(update, context) -> None:
        err = context.error
        user = getattr(update, "effective_user", None) if update is not None else None
        user_id = getattr(user, "id", None)
        if isinstance(err, Forbidden):
            logging.getLogger(__name__).warning(
                "telegram_forbidden user_id=%s detail=%s",
                user_id,
                err,
            )
            if user_id is not None:
                adapter.unbind_telegram(telegram_user_id=user_id)
            return
        logging.getLogger(__name__).exception("telegram_unhandled_error user_id=%s", user_id, exc_info=err)

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("unlink", handlers.unlink))
    app.add_handler(CommandHandler("parser_categ", handlers.parser_categ))
    app.add_handler(CommandHandler("parser_offer", handlers.parser_offer))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handlers.on_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    app.add_error_handler(on_error)

    async def run_nightly_pipeline(context) -> None:
        attempt = await pipeline.run_daily_pipeline(bot=context.bot, trigger="scheduled")
        if not attempt.started:
            logging.getLogger(__name__).warning("scheduled_skip reason=%s", attempt.message)

    async def post_init(application: Application) -> None:
        application.bot_data["sessions_flush_task"] = asyncio.create_task(_flush_sessions_loop(sessions=sessions))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PTBUserWarning)
            try:
                job_queue = application.job_queue
            except Exception:
                job_queue = None
        if job_queue is not None:
            job_queue.run_daily(
                run_nightly_pipeline,
                time=dt_time(hour=3, minute=0, tzinfo=bot_tz),
                name="nightly_pipeline",
            )
            logging.getLogger(__name__).info(
                "scheduler_registered job=nightly_pipeline time=03:00 timezone=%s",
                str(bot_tz),
            )
            return
        logging.getLogger(__name__).warning(
            "scheduler_fallback_enabled reason=job_queue_missing time=03:00 timezone=%s",
            str(bot_tz),
        )
        application.bot_data["nightly_fallback_task"] = asyncio.create_task(
            _run_daily_fallback(application=application, bot_tz=bot_tz, pipeline=pipeline)
        )

    async def post_shutdown(application: Application) -> None:
        flush_task = application.bot_data.get("sessions_flush_task")
        if flush_task is not None:
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
            await sessions.flush_all()
        task = application.bot_data.get("nightly_fallback_task")
        if task is None:
            pass
        else:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await sessions.close()

    app.post_init = post_init
    app.post_shutdown = post_shutdown
    return app


def run_polling() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    app = build_bot_application()
    app.run_polling(close_loop=False)
