from __future__ import annotations

from src.presentation.telegram.state.active_flow import ActiveFlow
from src.presentation.telegram.state.session_store import InMemorySessionStore


class TelegramFlowGuard:
    def __init__(self, *, sessions: InMemorySessionStore):
        self._sessions = sessions

    async def enter(self, telegram_user_id: int, flow: ActiveFlow) -> None:
        session = await self._sessions.get(telegram_user_id)
        session.active_flow = flow

    async def leave(self, telegram_user_id: int) -> None:
        session = await self._sessions.get(telegram_user_id)
        session.active_flow = None

    async def get_active_flow(self, telegram_user_id: int) -> ActiveFlow | None:
        session = await self._sessions.get(telegram_user_id)
        return session.active_flow

    async def is_active(self, telegram_user_id: int, flow: ActiveFlow) -> bool:
        session = await self._sessions.get(telegram_user_id)
        return session.active_flow == flow
