from __future__ import annotations

import asyncio
import logging
import warnings
from datetime import datetime, time as dt_time, timedelta

from telegram.error import Forbidden
from telegram.warnings import PTBUserWarning
from telegram.ext import Application

from src.presentation.telegram.bootstrap.handlers import register_telegram_handlers
from src.presentation.telegram.bootstrap.runtime import TelegramRuntime, build_telegram_runtime


async def _run_daily_fallback(*, application: Application, runtime: TelegramRuntime) -> None:
    logger = logging.getLogger(__name__)
    while True:
        now = datetime.now(runtime.bot_tz)
        target = datetime.combine(now.date(), dt_time(hour=3, minute=0), tzinfo=runtime.bot_tz)
        if now >= target:
            target = target + timedelta(days=1)
        sleep_seconds = max(1.0, (target - now).total_seconds())
        await asyncio.sleep(sleep_seconds)
        attempt = await runtime.pipeline.run_daily_pipeline(bot=application.bot, trigger="scheduled_fallback")
        if not attempt.started:
            logger.warning("scheduled_fallback_skip reason=%s", attempt.message)


async def _flush_sessions_loop(*, runtime: TelegramRuntime) -> None:
    while True:
        await asyncio.sleep(2.0)
        await runtime.sessions.flush_all()


def build_bot_application(*, runtime: TelegramRuntime | None = None) -> Application:
    actual_runtime = runtime or build_telegram_runtime()
    app = Application.builder().token(actual_runtime.settings.bot_token).build()
    register_telegram_handlers(app=app, handlers=actual_runtime.handlers)
    app.add_error_handler(_build_error_handler(runtime=actual_runtime))
    app.post_init = _build_post_init(runtime=actual_runtime)
    app.post_shutdown = _build_post_shutdown(runtime=actual_runtime)
    return app


def _build_error_handler(*, runtime: TelegramRuntime):
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
            runtime.services.admin.log_admin_event(
                event_type="telegram_blocked",
                status="success",
                user_id=user_id,
                message=str(err),
            )
            if user_id is not None:
                runtime.services.identity.unbind_telegram(telegram_user_id=user_id)
            return
        runtime.services.admin.log_admin_event(
            event_type="telegram_user_error",
            status="error",
            user_id=user_id,
            message=str(err),
        )
        logging.getLogger(__name__).exception("telegram_unhandled_error user_id=%s", user_id, exc_info=err)

    return on_error


def _build_post_init(*, runtime: TelegramRuntime):
    async def post_init(application: Application) -> None:
        application.bot_data["sessions_flush_task"] = asyncio.create_task(_flush_sessions_loop(runtime=runtime))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PTBUserWarning)
            try:
                job_queue = application.job_queue
            except Exception:
                job_queue = None
        if job_queue is not None:
            job_queue.run_daily(
                _build_nightly_job(runtime=runtime),
                time=dt_time(hour=3, minute=0, tzinfo=runtime.bot_tz),
                name="nightly_pipeline",
            )
            logging.getLogger(__name__).info(
                "scheduler_registered job=nightly_pipeline time=03:00 timezone=%s",
                str(runtime.bot_tz),
            )
            return
        logging.getLogger(__name__).warning(
            "scheduler_fallback_enabled reason=job_queue_missing time=03:00 timezone=%s",
            str(runtime.bot_tz),
        )
        application.bot_data["nightly_fallback_task"] = asyncio.create_task(
            _run_daily_fallback(application=application, runtime=runtime)
        )

    return post_init


def _build_post_shutdown(*, runtime: TelegramRuntime):
    async def post_shutdown(application: Application) -> None:
        flush_task = application.bot_data.get("sessions_flush_task")
        if flush_task is not None:
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
            await runtime.sessions.flush_all()
        task = application.bot_data.get("nightly_fallback_task")
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await runtime.sessions.close()

    return post_shutdown


def _build_nightly_job(*, runtime: TelegramRuntime):
    async def run_nightly_pipeline(context) -> None:
        attempt = await runtime.pipeline.run_daily_pipeline(bot=context.bot, trigger="scheduled")
        if not attempt.started:
            logging.getLogger(__name__).warning("scheduled_skip reason=%s", attempt.message)

    return run_nightly_pipeline
