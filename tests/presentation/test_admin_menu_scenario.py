from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace

from src.application.dto.travelline_publish_report import (
    TravellinePublishAdultsSummary,
    TravellinePublishDateStat,
    TravellinePublishRunReport,
)
from src.presentation.telegram.callbacks.data_parser import ADMIN_REPORT_TRAVELLINE_PUBLISH
from src.presentation.telegram.handlers.scenarios.admin_menu import AdminMenuScenario
from src.presentation.telegram.state.conversation_state import ConversationState


def _report() -> TravellinePublishRunReport:
    return TravellinePublishRunReport(
        run_id="tlpub_1",
        created_at=datetime(2026, 4, 6, 10, 0, 0),
        completed_at=datetime(2026, 4, 6, 10, 5, 0),
        mode="travelline_publish",
        validation_status="passed",
        validation_failure_reasons=tuple(),
        fallback_used=False,
        expected_dates_count=3,
        actual_dates_count=2,
        dates_with_no_categories_count=1,
        total_final_rows_count=12,
        tariff_pairing_anomalies_count=0,
        unmapped_categories_count=0,
        adults_summaries=(
            TravellinePublishAdultsSummary(
                adults_count=1,
                expected_requests_count=3,
                attempted_count=3,
                success_count=3,
                fail_count=0,
                collected_final_rows_count=8,
                status="completed_with_rows",
            ),
        ),
        empty_dates=(date(2026, 4, 7),),
        per_date_rows=(TravellinePublishDateStat(stay_date=date(2026, 4, 6), rows_count=8),),
    )


@dataclass
class _FakeSession:
    state: str


class _FakeSessions:
    def __init__(self, session: _FakeSession):
        self._session = session

    async def get(self, _telegram_user_id: int) -> _FakeSession:
        return self._session

    async def reset(self, _telegram_user_id: int) -> None:
        self._session.state = ConversationState.IDLE


class _FakeFlowGuard:
    async def is_active(self, _telegram_user_id: int, _flow) -> bool:
        return True

    async def enter(self, _telegram_user_id: int, _flow) -> None:
        return None


class _FakeMessage:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.documents: list[tuple[str, bytes, str | None]] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:
        self.texts.append(text)

    async def reply_document(self, document, filename: str, caption: str | None = None) -> None:
        self.documents.append((filename, document.getvalue(), caption))


class _FakeQuery:
    def __init__(self, message: _FakeMessage):
        self.message = message
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class _FakeAdminFacade:
    def __init__(self, report: TravellinePublishRunReport | None):
        self._report = report

    def get_admin_reports(self):
        return {}

    def get_latest_travelline_publish_report(self) -> TravellinePublishRunReport | None:
        return self._report


def test_admin_menu_sends_travelline_publish_summary_and_csv() -> None:
    deps = SimpleNamespace(
        admin=_FakeAdminFacade(_report()),
        sessions=_FakeSessions(_FakeSession(state=ConversationState.ADMIN_REPORTS)),
        flow_guard=_FakeFlowGuard(),
        admin_telegram_id=777,
        pipeline=SimpleNamespace(),
        identity=SimpleNamespace(resolve_guest_id=lambda telegram_user_id: None),
    )
    scenario = AdminMenuScenario(deps=deps)
    message = _FakeMessage()
    query = _FakeQuery(message)

    asyncio.run(
        scenario.handle_admin_callback(
            telegram_user_id=777,
            query=query,
            data=ADMIN_REPORT_TRAVELLINE_PUBLISH,
        )
    )

    assert query.answered is True
    assert len(message.texts) == 1
    assert "Travelline publish run" in message.texts[0]
    assert len(message.documents) == 1
    filename, payload, caption = message.documents[0]
    assert filename == "travelline_publish_last_run.csv"
    assert b"row_type,run_id,validation_status" in payload
    assert caption is not None


def test_admin_menu_handles_missing_travelline_publish_report() -> None:
    deps = SimpleNamespace(
        admin=_FakeAdminFacade(None),
        sessions=_FakeSessions(_FakeSession(state=ConversationState.ADMIN_REPORTS)),
        flow_guard=_FakeFlowGuard(),
        admin_telegram_id=777,
        pipeline=SimpleNamespace(),
        identity=SimpleNamespace(resolve_guest_id=lambda telegram_user_id: None),
    )
    scenario = AdminMenuScenario(deps=deps)
    message = _FakeMessage()
    query = _FakeQuery(message)

    asyncio.run(
        scenario.handle_admin_callback(
            telegram_user_id=777,
            query=query,
            data=ADMIN_REPORT_TRAVELLINE_PUBLISH,
        )
    )

    assert len(message.texts) == 1
    assert "отсутствует" in message.texts[0].lower()
    assert len(message.documents) == 1
