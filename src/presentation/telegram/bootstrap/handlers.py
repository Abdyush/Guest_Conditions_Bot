from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.presentation.telegram.handlers.bot_handlers import TelegramBotHandlers


def register_telegram_handlers(*, app: Application, handlers: TelegramBotHandlers) -> None:
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("unlink", handlers.unlink))
    app.add_handler(CommandHandler("parser_categ", handlers.parser_categ))
    app.add_handler(CommandHandler("parser_offer", handlers.parser_offer))
    app.add_handler(CommandHandler("admin_menu", handlers.admin_menu))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handlers.on_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
