from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.application.dto.admin_dashboard import AdminReport, AdminStatistics, DesiredPriceByGroupStat


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


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


def _format_rub(value_minor: int) -> str:
    rub = Decimal(value_minor) / Decimal("100")
    if rub == rub.to_integral():
        return f"{int(rub):,}".replace(",", " ") + " ₽"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " ₽"
