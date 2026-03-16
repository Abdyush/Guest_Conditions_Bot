from __future__ import annotations

from dataclasses import dataclass

from src.presentation.telegram.navigation.flow_guard import TelegramFlowGuard
from src.presentation.telegram.services.pipeline_orchestrator import PipelineOrchestrator
from src.presentation.telegram.services.use_cases_adapter import TelegramUseCasesAdapter
from src.presentation.telegram.state.session_store import InMemorySessionStore


@dataclass(frozen=True, slots=True)
class TelegramHandlersDependencies:
    adapter: TelegramUseCasesAdapter
    sessions: InMemorySessionStore
    pipeline: PipelineOrchestrator
    flow_guard: TelegramFlowGuard
