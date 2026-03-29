from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from threading import Lock
from time import perf_counter
from types import TracebackType

from src.domain.entities.rate import DailyRate
from src.infrastructure.selenium.browser import build_chrome_options
from src.infrastructure.selenium.hotel_rates_gateway import SeleniumHotelRatesGateway
from src.infrastructure.selenium.rates_transform import map_scraped_rates_to_domain


@dataclass(frozen=True, slots=True)
class RatesParallelRunConfig:
    category_to_group: dict[str, str]
    adults_counts: tuple[int, ...]
    days_to_collect: int = 3
    headless: bool = True
    wait_seconds: int = 20


@dataclass(frozen=True, slots=True)
class ParserRunOutcome:
    adults_count: int
    rates: tuple[DailyRate, ...]
    total_found: int = 0
    total_collected: int = 0
    failed_fn: str | None = None
    elapsed_seconds: float = 0.0


def build_stay_dates(start_date: date, days_to_collect: int) -> list[date]:
    if days_to_collect <= 0:
        raise ValueError("days_to_collect must be > 0")
    return [start_date + timedelta(days=offset) for offset in range(days_to_collect)]


class SeleniumRatesParallelRunner:
    def __init__(self, config: RatesParallelRunConfig):
        if not config.category_to_group:
            raise ValueError("category_to_group must not be empty; seed category_rules in Postgres first")
        if not config.adults_counts:
            raise ValueError("adults_counts must not be empty")
        for adults in config.adults_counts:
            if adults <= 0:
                raise ValueError("adults_counts must contain only positive values")
        self._config = config
        self._log_lock = Lock()

    def run(self, *, start_date: date) -> list[DailyRate]:
        run_started_at = perf_counter()
        try:
            from selenium import webdriver
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "Selenium is required for parallel rates runner. Install `selenium` and ChromeDriver."
            ) from exc

        stay_dates = build_stay_dates(start_date, self._config.days_to_collect)
        out: list[DailyRate] = []
        outcomes: list[ParserRunOutcome] = []
        max_workers = len(self._config.adults_counts)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_adults = {
                pool.submit(
                    self._run_single_parser,
                    webdriver=webdriver,
                    category_to_group=self._config.category_to_group,
                    adults_count=adults_count,
                    stay_dates=stay_dates,
                ): adults_count
                for adults_count in self._config.adults_counts
            }
            for future in as_completed(future_to_adults):
                adults_count = future_to_adults[future]
                try:
                    outcome = future.result()
                except Exception as exc:
                    fn_name = self._extract_fn_name(exc.__traceback__)
                    outcome = ParserRunOutcome(
                        adults_count=adults_count,
                        rates=tuple(),
                        total_found=0,
                        total_collected=0,
                        failed_fn=fn_name,
                        elapsed_seconds=0.0,
                    )
                    msg = self._short_error_text(exc)
                    self._log(
                        f"РћРЁРР‘РљРђ, РїР°СЂСЃРµСЂ ({self._adults_label(adults_count)}), "
                        f"(1 РґРµРЅСЊ РёР· {len(stay_dates)}) {fn_name}, {msg}"
                    )
                outcomes.append(outcome)
                out.extend(outcome.rates)

        total_elapsed = self._format_duration(perf_counter() - run_started_at)
        self._log(f"РџР°СЂСЃРёРЅРі РєР°С‚РµРіРѕСЂРёР№ Р·Р°РєРѕРЅС‡РµРЅ, РѕР±С‰РµРµ РІСЂРµРјСЏ {total_elapsed}")
        success_count = sum(1 for x in outcomes if x.failed_fn is None)
        self._log(
            f"РёР· {len(self._config.adults_counts)} РїР°СЂСЃРµСЂРѕРІ "
            f"{success_count} СѓСЃРїРµС€РЅРѕ РІС‹РїРѕР»РЅРёР»Рё СЂР°Р±РѕС‚Сѓ"
        )
        self._log("")
        for outcome in sorted(outcomes, key=lambda x: x.adults_count):
            if outcome.failed_fn is not None:
                self._log(
                    f"РїР°СЂСЃРµСЂ ({self._adults_label(outcome.adults_count)}) "
                    f"СЃР»РѕРјР°Р»СЃСЏ: {outcome.failed_fn}"
                )
                continue
            self._log(
                f"РїР°СЂСЃРµСЂ ({self._adults_label(outcome.adults_count)}) СѓСЃРїРµС€РЅРѕ: "
                f"РёР· {outcome.total_found} РЅР°Р№РґРµРЅРЅС‹С…, СЃРѕР±СЂР°Р» {outcome.total_collected}, "
                f"РІСЂРµРјСЏ {self._format_duration(outcome.elapsed_seconds)}"
            )

        return out

    def _run_single_parser(
        self,
        *,
        webdriver,
        category_to_group: dict[str, str],
        adults_count: int,
        stay_dates: list[date],
    ) -> ParserRunOutcome:
        adults_label = self._adults_label(adults_count)
        days_total = len(stay_dates)
        parser_started_at = perf_counter()

        self._log(f"РїР°СЂСЃРµСЂ ({adults_label}) РЅР°С‡Р°Р» СЂР°Р±РѕС‚Сѓ")
        parsed: list[DailyRate] = []
        failed_fn: str | None = None
        totals = {"found": 0, "collected": 0}
        try:
            options = build_chrome_options(headless=self._config.headless)
            with webdriver.Chrome(options=options) as browser:
                try:
                    gateway = SeleniumHotelRatesGateway(
                        browser,
                        adults_count=adults_count,
                        wait_seconds=self._config.wait_seconds,
                    )
                except Exception as exc:
                    fn_name = self._extract_fn_name(exc.__traceback__)
                    msg = self._short_error_text(exc)
                    self._log(f"РћРЁРР‘РљРђ, РїР°СЂСЃРµСЂ ({adults_label}), (1 РґРµРЅСЊ РёР· {days_total}) {fn_name}, {msg}")
                    failed_fn = fn_name
                    return ParserRunOutcome(
                        adults_count=adults_count,
                        rates=tuple(parsed),
                        total_found=totals["found"],
                        total_collected=totals["collected"],
                        failed_fn=failed_fn,
                        elapsed_seconds=perf_counter() - parser_started_at,
                    )
                for day_index, stay_date in enumerate(stay_dates, start=1):
                    try:
                        self._install_day_logging_hooks(
                            gateway=gateway,
                            adults_label=adults_label,
                            day_index=day_index,
                            days_total=days_total,
                            stay_date=stay_date,
                            totals=totals,
                        )
                        scraped = gateway.get_rates_for_date(stay_date)
                        parsed.extend(
                            map_scraped_rates_to_domain(
                                scraped,
                                category_to_group=self._config.category_to_group,
                                adults_counts=[adults_count],
                            )
                        )
                    except Exception as exc:
                        fn_name = self._extract_fn_name(exc.__traceback__)
                        if failed_fn is None:
                            failed_fn = fn_name
                        msg = self._short_error_text(exc)
                        self._log(
                            f"РћРЁРР‘РљРђ, РїР°СЂСЃРµСЂ ({adults_label}), ({day_index} РґРµРЅСЊ РёР· {days_total}) "
                            f"{fn_name}, {msg}"
                        )
        finally:
            self._log(f"РїР°СЂСЃРµСЂ ({adults_label}) Р·Р°РєРѕРЅС‡РёР» СЂР°Р±РѕС‚Сѓ")

        return ParserRunOutcome(
            adults_count=adults_count,
            rates=tuple(parsed),
            total_found=totals["found"],
            total_collected=totals["collected"],
            failed_fn=failed_fn,
            elapsed_seconds=perf_counter() - parser_started_at,
        )

    def _install_day_logging_hooks(
        self,
        *,
        gateway: SeleniumHotelRatesGateway,
        adults_label: str,
        day_index: int,
        days_total: int,
        stay_date: date,
        totals: dict[str, int],
    ) -> None:
        original_find_categories = SeleniumHotelRatesGateway._find_categories.__get__(gateway, SeleniumHotelRatesGateway)
        original_extract_rate = SeleniumHotelRatesGateway._extract_current_category_rate.__get__(
            gateway, SeleniumHotelRatesGateway
        )

        state = {"total": None, "collected": 0}
        date_label = stay_date.strftime("%d.%m.%y")

        def logged_find_categories():
            categories = original_find_categories()
            if state["total"] is None:
                state["total"] = len(categories)
                totals["found"] += state["total"]
                self._log(
                    f"РїР°СЂСЃРµСЂ ({adults_label}), ({day_index} РґРµРЅСЊ РёР· {days_total}) "
                    f"РЅР°С€РµР» {state['total']} РєР°С‚РµРіРѕСЂРёР№ РЅР° РґР°С‚Сѓ {date_label}"
                )
            return categories

        def logged_extract_rate(*args, **kwargs):
            item = original_extract_rate(*args, **kwargs)
            if item is not None:
                state["collected"] += 1
                totals["collected"] += 1
                total = state["total"] if state["total"] is not None else "?"
                self._log(
                    f"РїР°СЂСЃРµСЂ ({adults_label}), ({day_index} РґРµРЅСЊ РёР· {days_total}), "
                    f"СЃРѕР±СЂР°Р» РґР°РЅРЅС‹Рµ {state['collected']} РєР°С‚РµРіРѕСЂРёРё РёР· {total} РЅР° РґР°С‚Сѓ {date_label}"
                )
            return item

        gateway._find_categories = logged_find_categories
        gateway._extract_current_category_rate = logged_extract_rate

    def _log(self, message: str) -> None:
        with self._log_lock:
            print(message)

    @staticmethod
    def _adults_label(adults_count: int) -> str:
        if adults_count == 1:
            return "1 РІР·СЂРѕСЃР»С‹Р№"
        return f"{adults_count} РІР·СЂРѕСЃР»С‹С…"

    @staticmethod
    def _extract_fn_name(traceback: TracebackType | None) -> str:
        if traceback is None:
            return "<unknown>"
        current = traceback
        while current.tb_next is not None:
            current = current.tb_next
        return current.tb_frame.f_code.co_name

    @staticmethod
    def _short_error_text(exc: Exception) -> str:
        text = str(exc).strip()
        if not text:
            return "<empty error>"
        first_line = text.splitlines()[0].strip()
        if first_line.startswith("Message:"):
            return first_line
        return f"Message: {first_line}"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours} С‡Р°СЃ. {minutes} РјРёРЅ. {secs} СЃРµРє."
