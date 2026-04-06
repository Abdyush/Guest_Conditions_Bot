from __future__ import annotations

import csv
from io import StringIO
from datetime import datetime
from decimal import Decimal

from src.application.dto.admin_dashboard import AdminReport, AdminStatistics, DesiredPriceByGroupStat
from src.application.dto.travelline_publish_report import TravellinePublishRunReport


def render_admin_main() -> str:
    return "Меню администратора"


def render_admin_system_menu() -> str:
    return "Система"


def render_admin_reports_menu() -> str:
    return "Отчеты"


def render_admin_statistics_menu() -> str:
    return "Статистика"


def render_admin_access_denied() -> str:
    return "Команда недоступна."


def render_admin_main_reply_hint() -> str:
    return "Доступна кнопка «Меню гостя»."


def render_admin_submenu_reply_hint() -> str:
    return "Используйте кнопки ниже для возврата или выхода."


def render_system_attempt_result(*, title: str, attempt_started: bool, attempt_message: str) -> str:
    if not attempt_started and attempt_message.startswith("busy:"):
        return f"{title}: процесс уже выполняется."
    if not attempt_started:
        return f"{title}: не удалось выполнить запуск."
    return f"{title}: запуск выполнен."


def render_admin_report(report: AdminReport) -> str:
    lines = [
        report.title,
        "",
        f"Всего запусков: {report.total_runs}",
        f"Успешно: {report.success_runs}",
        f"С ошибкой: {report.error_runs}",
        f"Занято: {report.busy_runs}",
        f"Последний запуск: {_format_datetime(report.last_run_at)}",
    ]
    if report.recent_entries:
        lines.append("")
        lines.append("Последние записи:")
        for item in report.recent_entries[:5]:
            trigger = item.trigger or "—"
            message = item.message or "—"
            lines.append(f"• {_format_datetime(item.created_at)} | {item.status} | {trigger} | {message}")
    else:
        lines.append("")
        lines.append("За последнюю неделю записей нет.")
    return "\n".join(lines)


def render_total_users(total_users: int) -> str:
    return f"Всего пользователей: {total_users}"


def render_new_users_last_week(value: int | None) -> str:
    if value is None:
        return "Новые пользователи за последнюю неделю: данные недоступны."
    return f"Новые пользователи за последнюю неделю: {value}"


def render_blocked_users_last_week(value: int | None) -> str:
    if value is None:
        return "Заблокировавшие бота за последнюю неделю: данные недоступны."
    return f"Заблокировавшие бота за последнюю неделю: {value}"


def render_price_expectations_table(stats: list[DesiredPriceByGroupStat]) -> str:
    lines = ["Желаемые цены по группам категорий"]
    if not stats:
        lines.append("")
        lines.append("Данных нет.")
        return "\n".join(lines)
    for item in stats:
        lines.extend(
            [
                "",
                f"{item.group_id}",
                f"Пользователей: {item.users_count}",
                f"Средняя цена: {_format_rub(item.avg_price_minor)}",
                f"Минимум: {_format_rub(item.min_price_minor)}",
                f"Максимум: {_format_rub(item.max_price_minor)}",
            ]
        )
    return "\n".join(lines)


def render_travelline_publish_report_summary(report: TravellinePublishRunReport | None) -> str:
    if report is None:
        return "Отчет по последнему Travelline publish run пока отсутствует."

    adults_status_counts: dict[str, int] = {}
    for item in report.adults_summaries:
        adults_status_counts[item.status] = adults_status_counts.get(item.status, 0) + 1
    adults_summary = ", ".join(
        f"{status}={count}" for status, count in sorted(adults_status_counts.items())
    ) or "нет данных"
    reasons = "; ".join(report.validation_failure_reasons) if report.validation_failure_reasons else "—"

    return "\n".join(
        [
            "Последний Travelline publish run",
            "",
            f"Статус: {report.validation_status}",
            f"Fallback used: {'yes' if report.fallback_used else 'no'}",
            f"Rows: {report.total_final_rows_count}",
            f"Expected dates: {report.expected_dates_count}",
            f"Actual dates: {report.actual_dates_count}",
            f"Dates with no categories: {report.dates_with_no_categories_count}",
            f"Tariff anomalies: {report.tariff_pairing_anomalies_count}",
            f"Unmapped categories: {report.unmapped_categories_count}",
            f"Adults summary: {adults_summary}",
            f"Validation reasons: {reasons}",
            f"Completed at: {_format_datetime(report.completed_at)}",
        ]
    )


def build_travelline_publish_report_csv(report: TravellinePublishRunReport | None) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "row_type",
            "run_id",
            "validation_status",
            "fallback_used",
            "created_at",
            "completed_at",
            "validation_failure_reasons",
            "expected_dates_count",
            "actual_dates_count",
            "dates_with_no_categories_count",
            "total_final_rows_count",
            "tariff_pairing_anomalies_count",
            "unmapped_categories_count",
            "adults_count",
            "expected_requests_count",
            "attempted_count",
            "success_count",
            "fail_count",
            "collected_final_rows_count",
            "adults_status",
            "date",
            "rows_count",
        ],
    )
    writer.writeheader()
    if report is None:
        return buffer.getvalue().encode("utf-8")

    writer.writerow(
        {
            "row_type": "summary",
            "run_id": report.run_id,
            "validation_status": report.validation_status,
            "fallback_used": report.fallback_used,
            "created_at": report.created_at.isoformat(sep=" "),
            "completed_at": report.completed_at.isoformat(sep=" "),
            "validation_failure_reasons": "; ".join(report.validation_failure_reasons),
            "expected_dates_count": report.expected_dates_count,
            "actual_dates_count": report.actual_dates_count,
            "dates_with_no_categories_count": report.dates_with_no_categories_count,
            "total_final_rows_count": report.total_final_rows_count,
            "tariff_pairing_anomalies_count": report.tariff_pairing_anomalies_count,
            "unmapped_categories_count": report.unmapped_categories_count,
        }
    )
    for item in report.adults_summaries:
        writer.writerow(
            {
                "row_type": "adults",
                "run_id": report.run_id,
                "adults_count": item.adults_count,
                "expected_requests_count": item.expected_requests_count,
                "attempted_count": item.attempted_count,
                "success_count": item.success_count,
                "fail_count": item.fail_count,
                "collected_final_rows_count": item.collected_final_rows_count,
                "adults_status": item.status,
            }
        )
    for stay_date in report.empty_dates:
        writer.writerow(
            {
                "row_type": "empty_date",
                "run_id": report.run_id,
                "date": stay_date.isoformat(),
            }
        )
    for item in report.per_date_rows:
        writer.writerow(
            {
                "row_type": "date_rows",
                "run_id": report.run_id,
                "date": item.stay_date.isoformat(),
                "rows_count": item.rows_count,
            }
        )
    return buffer.getvalue().encode("utf-8")


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


def _format_rub(value_minor: int) -> str:
    rub = Decimal(value_minor) / Decimal("100")
    if rub == rub.to_integral():
        return f"{int(rub):,}".replace(",", " ") + " ₽"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " ₽"
