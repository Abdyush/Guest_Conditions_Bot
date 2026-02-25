from __future__ import annotations

from src.presentation.telegram.state.conversation_state import ConversationState
from src.presentation.telegram.state.session_store import InMemorySessionStore


def test_session_store_state_transitions() -> None:
    store = InMemorySessionStore()
    user_id = 123

    assert store.get(user_id).state == ConversationState.IDLE
    store.set_state(user_id, ConversationState.AWAIT_BIND_GUEST_ID)
    assert store.get(user_id).state == ConversationState.AWAIT_BIND_GUEST_ID
    store.reset(user_id)
    assert store.get(user_id).state == ConversationState.IDLE

