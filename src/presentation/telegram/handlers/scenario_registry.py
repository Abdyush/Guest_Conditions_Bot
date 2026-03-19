from __future__ import annotations

from dataclasses import dataclass

from src.presentation.telegram.handlers.scenarios.admin_commands import AdminCommandsScenario
from src.presentation.telegram.handlers.scenarios.admin_menu import AdminMenuScenario
from src.presentation.telegram.handlers.scenarios.available_offers import AvailableOffersScenario
from src.presentation.telegram.handlers.scenarios.best_periods import BestPeriodsScenario
from src.presentation.telegram.handlers.scenarios.notification_offers import NotificationOffersScenario
from src.presentation.telegram.handlers.scenarios.onboarding import OnboardingScenario
from src.presentation.telegram.handlers.scenarios.period_quotes import PeriodQuotesScenario
from src.presentation.telegram.handlers.scenarios.registration import RegistrationScenario


@dataclass(frozen=True, slots=True)
class TelegramScenarioRegistry:
    onboarding: OnboardingScenario
    registration: RegistrationScenario
    admin_menu: AdminMenuScenario
    best_periods: BestPeriodsScenario
    period_quotes: PeriodQuotesScenario
    available_offers: AvailableOffersScenario
    notification_offers: NotificationOffersScenario
    admin_commands: AdminCommandsScenario
