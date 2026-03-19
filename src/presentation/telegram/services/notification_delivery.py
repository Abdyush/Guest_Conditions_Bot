from __future__ import annotations

import logging
from collections.abc import Sequence

from telegram import Bot
from telegram.error import TelegramError

from src.application.dto.guest_notification_batch import GuestNotificationBatch
from src.infrastructure.orchestration.pipeline_orchestrator import NotificationDeliveryResult
from src.presentation.telegram.keyboards.notification_offers import (
    build_notification_groups_inline_keyboard,
    build_notification_scenario_keyboard,
)
from src.presentation.telegram.presenters.available_presenter import build_available_groups
from src.presentation.telegram.presenters.notification_offers_presenter import (
    render_notification_groups_prompt,
    render_notification_intro,
)


logger = logging.getLogger(__name__)


class TelegramNotificationDelivery:
    async def deliver_batches(
        self,
        *,
        bot: object | None,
        targets: Sequence[GuestNotificationBatch],
    ) -> NotificationDeliveryResult:
        if bot is None:
            logger.warning("notifications_skip reason=no_bot_instance")
            return NotificationDeliveryResult(sent_recipients=0, delivered_targets=())

        telegram_bot = bot if isinstance(bot, Bot) else None
        if telegram_bot is None:
            logger.warning("notifications_skip reason=invalid_bot_instance type=%s", type(bot).__name__)
            return NotificationDeliveryResult(sent_recipients=0, delivered_targets=())

        sent_recipients = 0
        delivered_targets: list[GuestNotificationBatch] = []
        for target in targets:
            sent_for_guest = False
            group_names = [group.label for group in build_available_groups(category_groups=target.category_groups)]
            intro_text = render_notification_intro(guest_name=target.guest_name)
            groups_text = render_notification_groups_prompt()
            markup = build_notification_groups_inline_keyboard(run_id=target.run_id, group_names=group_names)

            for telegram_user_id in target.telegram_user_ids:
                try:
                    await telegram_bot.send_message(
                        chat_id=telegram_user_id,
                        text=intro_text,
                        reply_markup=build_notification_scenario_keyboard(),
                    )
                    await telegram_bot.send_message(
                        chat_id=telegram_user_id,
                        text=groups_text,
                        reply_markup=markup,
                    )
                    sent_for_guest = True
                    sent_recipients += 1
                except TelegramError:
                    logger.exception(
                        "notification_send_error guest_id=%s telegram_user_id=%s",
                        target.guest_id,
                        telegram_user_id,
                    )

            if sent_for_guest:
                delivered_targets.append(target)

        return NotificationDeliveryResult(
            sent_recipients=sent_recipients,
            delivered_targets=tuple(delivered_targets),
        )
