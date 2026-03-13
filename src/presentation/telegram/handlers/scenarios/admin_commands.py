from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies


logger = logging.getLogger(__name__)


class AdminCommandsScenario:
    def __init__(self, *, deps: TelegramHandlersDependencies):
        self._deps = deps

    async def parser_categ(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        logger.info("telegram_update type=command user_id=%s command=/parser_categ", user.id)
        attempt = await self._deps.pipeline.run_categories_parser(trigger=f"manual:telegram:{user.id}")
        if not attempt.started:
            if attempt.message.startswith("busy:"):
                await message.reply_text("Запуск отклонен: уже выполняется другой процесс.")
                return
            await message.reply_text("Ошибка запуска парсера цен. Проверьте логи.")
            return
        await message.reply_text("Парсер цен завершен успешно.")

    async def parser_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        message = update.effective_message
        if user is None or message is None:
            return
        logger.info("telegram_update type=command user_id=%s command=/parser_offer", user.id)
        attempt = await self._deps.pipeline.run_offers_parser(trigger=f"manual:telegram:{user.id}")
        if not attempt.started:
            if attempt.message.startswith("busy:"):
                await message.reply_text("Запуск отклонен: уже выполняется другой процесс.")
                return
            await message.reply_text("Ошибка запуска парсера спецпредложений. Проверьте логи.")
            return
        await message.reply_text("Парсер спецпредложений завершен успешно.")
