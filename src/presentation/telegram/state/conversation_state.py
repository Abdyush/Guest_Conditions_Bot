from __future__ import annotations

from enum import Enum


class ConversationState(str, Enum):
    IDLE = "idle"
    AWAIT_BIND_GUEST_ID = "await_bind_guest_id"
    AWAIT_PHONE_CONTACT = "await_phone_contact"
    AWAIT_REG_NAME = "await_reg_name"
    AWAIT_REG_ADULTS = "await_reg_adults"
    AWAIT_REG_CHILDREN_4_13 = "await_reg_children_4_13"
    AWAIT_REG_INFANTS_0_3 = "await_reg_infants_0_3"
    AWAIT_REG_GROUPS = "await_reg_groups"
    AWAIT_REG_LOYALTY = "await_reg_loyalty"
    AWAIT_REG_BANK = "await_reg_bank"
    AWAIT_REG_DESIRED_PRICE = "await_reg_desired_price"
    EDIT_MENU = "edit_menu"
    EDIT_ADULTS = "edit_adults"
    EDIT_CHILDREN_4_13 = "edit_children_4_13"
    EDIT_INFANTS_0_3 = "edit_infants_0_3"
    EDIT_GROUPS = "edit_groups"
    EDIT_LOYALTY = "edit_loyalty"
    EDIT_BANK = "edit_bank"
    EDIT_DESIRED_PRICE = "edit_desired_price"
    AWAIT_BEST_GROUP_ID = "await_best_group_id"
    AWAIT_QUOTES_GROUP = "await_quotes_group"
    AWAIT_QUOTES_CALENDAR = "await_quotes_calendar"
    AWAIT_QUOTES_CATEGORY = "await_quotes_category"
