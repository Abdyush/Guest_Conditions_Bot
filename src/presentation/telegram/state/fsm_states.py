from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

from src.presentation.telegram.state.conversation_state import ConversationState


class ConversationFSM(StatesGroup):
    idle = State()
    await_bind_guest_id = State()
    await_phone_contact = State()
    await_reg_name = State()
    await_reg_adults = State()
    await_reg_children_4_13 = State()
    await_reg_infants_0_3 = State()
    await_reg_groups = State()
    await_reg_loyalty = State()
    await_reg_bank = State()
    await_reg_desired_price = State()
    edit_menu = State()
    edit_adults = State()
    edit_children_4_13 = State()
    edit_infants_0_3 = State()
    edit_groups = State()
    edit_loyalty = State()
    edit_bank = State()
    edit_desired_price = State()
    await_best_group_id = State()
    await_best_category_id = State()
    await_quotes_group = State()
    await_quotes_calendar = State()
    await_quotes_category = State()


STATE_TO_FSM: dict[ConversationState, State] = {
    ConversationState.IDLE: ConversationFSM.idle,
    ConversationState.AWAIT_BIND_GUEST_ID: ConversationFSM.await_bind_guest_id,
    ConversationState.AWAIT_PHONE_CONTACT: ConversationFSM.await_phone_contact,
    ConversationState.AWAIT_REG_NAME: ConversationFSM.await_reg_name,
    ConversationState.AWAIT_REG_ADULTS: ConversationFSM.await_reg_adults,
    ConversationState.AWAIT_REG_CHILDREN_4_13: ConversationFSM.await_reg_children_4_13,
    ConversationState.AWAIT_REG_INFANTS_0_3: ConversationFSM.await_reg_infants_0_3,
    ConversationState.AWAIT_REG_GROUPS: ConversationFSM.await_reg_groups,
    ConversationState.AWAIT_REG_LOYALTY: ConversationFSM.await_reg_loyalty,
    ConversationState.AWAIT_REG_BANK: ConversationFSM.await_reg_bank,
    ConversationState.AWAIT_REG_DESIRED_PRICE: ConversationFSM.await_reg_desired_price,
    ConversationState.EDIT_MENU: ConversationFSM.edit_menu,
    ConversationState.EDIT_ADULTS: ConversationFSM.edit_adults,
    ConversationState.EDIT_CHILDREN_4_13: ConversationFSM.edit_children_4_13,
    ConversationState.EDIT_INFANTS_0_3: ConversationFSM.edit_infants_0_3,
    ConversationState.EDIT_GROUPS: ConversationFSM.edit_groups,
    ConversationState.EDIT_LOYALTY: ConversationFSM.edit_loyalty,
    ConversationState.EDIT_BANK: ConversationFSM.edit_bank,
    ConversationState.EDIT_DESIRED_PRICE: ConversationFSM.edit_desired_price,
    ConversationState.AWAIT_BEST_GROUP_ID: ConversationFSM.await_best_group_id,
    ConversationState.AWAIT_BEST_CATEGORY_ID: ConversationFSM.await_best_category_id,
    ConversationState.AWAIT_QUOTES_GROUP: ConversationFSM.await_quotes_group,
    ConversationState.AWAIT_QUOTES_CALENDAR: ConversationFSM.await_quotes_calendar,
    ConversationState.AWAIT_QUOTES_CATEGORY: ConversationFSM.await_quotes_category,
}

FSM_TO_STATE: dict[str, ConversationState] = {
    fsm_state.state: state for state, fsm_state in STATE_TO_FSM.items()
}
