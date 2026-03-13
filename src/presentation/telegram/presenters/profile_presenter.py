from __future__ import annotations

from src.domain.entities.guest_preferences import GuestPreferences
from src.presentation.telegram.ui_texts import CATEGORY_LABEL_TO_CODE


def render_profile(profile: GuestPreferences) -> str:
    code_to_label = {v: k for k, v in CATEGORY_LABEL_TO_CODE.items()}
    groups = sorted(profile.effective_allowed_groups or set())
    group_lines = [f" - {code_to_label.get(g, g)}" for g in groups] if groups else [" - \u2014"]
    loyalty = profile.loyalty_status.value.capitalize() if profile.loyalty_status else "\u2014"
    bank = profile.bank_status.value if profile.bank_status else "\u043d\u0435\u0442"
    desired = profile.desired_price_per_night.round_rubles()
    name = profile.guest_name or "\u0413\u043e\u0441\u0442\u044c"
    return (
        "\u0412\u0430\u0448\u0438 \u0434\u0430\u043d\u043d\u044b\u0435:\n"
        f" \u0418\u043c\u044f: {name}\n"
        f" \u0412\u0437\u0440\u043e\u0441\u043b\u044b\u0445: {profile.occupancy.adults}\n"
        f" \u0414\u0435\u0442\u0435\u0439 4\u201317: {profile.occupancy.children_4_13}\n"
        f" \u0414\u0435\u0442\u0435\u0439 0\u20133: {profile.occupancy.infants}\n"
        " \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438:\n"
        f"{chr(10).join(group_lines)}\n"
        f" \u0421\u0442\u0430\u0442\u0443\u0441 \u043b\u043e\u044f\u043b\u044c\u043d\u043e\u0441\u0442\u0438: {loyalty}\n"
        f" \u0421\u0442\u0430\u0442\u0443\u0441 \u0432 \u0421\u0431\u0435\u0440\u0435: {bank}\n"
        f" \u0416\u0435\u043b\u0430\u0435\u043c\u0430\u044f \u0446\u0435\u043d\u0430: {desired} \u20bd"
    )
