from __future__ import annotations

import logging
import os

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
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("unlink", handlers.unlink))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handlers.on_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
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
