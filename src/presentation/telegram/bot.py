from __future__ import annotations

import logging

from telegram.ext import Application

from src.presentation.telegram.bootstrap.application import build_bot_application as _build_bot_application


def build_bot_application() -> Application:
    return _build_bot_application()


def run_polling() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    app = build_bot_application()
    app.run_polling(close_loop=False)
