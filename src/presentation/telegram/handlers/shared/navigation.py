from __future__ import annotations

from src.presentation.telegram.handlers.dependencies import TelegramHandlersDependencies
from src.presentation.telegram.keyboards.main_menu import build_main_menu_keyboard, build_phone_request_keyboard
from src.presentation.telegram.presenters.profile_presenter import render_profile
from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.ui_texts import msg


async def send_main_menu_for_guest(*, deps: TelegramHandlersDependencies, message, guest_id: str) -> None:
    profile = deps.adapter.get_guest_profile(guest_id=guest_id)
    if profile is None:
        user = getattr(message, "from_user", None)
        if user is not None and getattr(user, "id", None) is not None:
            deps.adapter.unbind_telegram(telegram_user_id=user.id)
            await deps.sessions.set_state(user.id, ConversationState.AWAIT_PHONE_CONTACT)
        await message.reply_text(
            f"{msg('profile_not_found')}\n{msg('ask_phone')}",
            reply_markup=build_phone_request_keyboard(),
        )
        return
    await message.reply_text(render_profile(profile), reply_markup=build_main_menu_keyboard())
