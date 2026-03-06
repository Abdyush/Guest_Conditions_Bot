from __future__ import annotations

import logging
import os

from telegram.error import Forbidden
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.presentation.telegram.handlers.bot_handlers import TelegramBotHandlers
from src.presentation.telegram.services.use_cases_adapter import TelegramUseCasesAdapter
from src.presentation.telegram.state.session_store import InMemorySessionStore


def build_bot_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    adapter = TelegramUseCasesAdapter()
    sessions = InMemorySessionStore()
    handlers = TelegramBotHandlers(adapter=adapter, sessions=sessions)

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
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handlers.on_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    app.add_error_handler(on_error)
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
