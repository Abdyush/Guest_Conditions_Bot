from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from src.domain.entities.offer import Offer
from src.infrastructure.contracts.offer_input import DateRangeInput, OfferInput
from src.infrastructure.mappers.to_domain import map_offers


class OffersTransformError(RuntimeError):
    pass


def _normalize_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def _pick(payload: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for key, value in payload.items():
        key_norm = _normalize_key(str(key))
        if any(alias in key_norm for alias in aliases):
            return value
    return None


def _parse_dmy(raw: str) -> date:
    normalized = str(raw).strip().replace("/", ".")
    day_s, month_s, year_s = normalized.split(".")
    year = int(year_s)
    if year < 100:
        year += 2000
    return date(year, int(month_s), int(day_s))


def _parse_ranges(value: Any) -> list[DateRangeInput]:
    if not isinstance(value, list):
        return []
    out: list[DateRangeInput] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            start = _parse_dmy(item[0])
            end_inclusive = _parse_dmy(item[1])
        except Exception:
            continue
        if end_inclusive < start:
            continue
        out.append(DateRangeInput(start=start, end=end_inclusive + timedelta(days=1)))
    return out


def _extract_discount(raw_formula: str, raw_text: str) -> tuple[str, dict[str, Any]] | None:
    formula_match = re.search(r"([01](?:[.,]\d+)?)", raw_formula.replace(" ", ""))
    if formula_match:
        coef = Decimal(formula_match.group(1).replace(",", "."))
        if Decimal("0") < coef < Decimal("1"):
            return "PERCENT_OFF", {"percent": Decimal("1") - coef}

    pay_get = re.search(r"(\d+)\s*=\s*(\d+)", raw_formula + "\n" + raw_text)
    if pay_get:
        a = int(pay_get.group(1))
        b = int(pay_get.group(2))
        x, y = min(a, b), max(a, b)
        if 0 < x < y:
            return "PAY_X_GET_Y", {"x": x, "y": y}

    pct = re.search(r"(\d{1,2})\s*%", raw_text)
    if pct:
        value = int(pct.group(1))
        if 0 < value < 100:
            return "PERCENT_OFF", {"percent": Decimal(value) / Decimal("100")}
    return None


def _parse_min_nights(value: Any, raw_text: str) -> int:
    try:
        parsed = int(str(value).strip())
        if parsed > 0:
            return parsed
    except Exception:
        pass
    match = re.search(r"(\d+)\s*(?:ноч|сут)", raw_text.casefold())
    if match:
        parsed = int(match.group(1))
        if parsed > 0:
            return parsed
    return 1


def _normalize_categories(raw_categories: Any) -> list[str] | None:
    if isinstance(raw_categories, str):
        text = raw_categories.strip()
        if not text or "все катег" in text.casefold() or "все вилл" in text.casefold():
            return None
        return [text]
    if isinstance(raw_categories, list):
        categories = [str(item).strip() for item in raw_categories if str(item).strip()]
        return categories or None
    return None


def _is_all_villas(raw_categories: Any) -> bool:
    return isinstance(raw_categories, str) and "все вилл" in raw_categories.casefold()


def _expand_all_villas_categories(category_to_group: dict[str, str]) -> list[str] | None:
    categories = [
        category
        for category in category_to_group.keys()
        if ("вилл" in _normalize_key(category) or "villa" in _normalize_key(category))
    ]
    categories = sorted(set(categories))
    return categories or None


def _offer_id(title: str, raw_text: str) -> str:
    base = (title + "\n" + raw_text).encode("utf-8", errors="ignore")
    return "selenium_offer_" + hashlib.sha1(base).hexdigest()[:16]


def map_legacy_scraped_offers_to_domain(
    scraped_offers: list[dict[str, Any]],
    *,
    category_to_group: dict[str, str],
    fail_fast: bool = False,
) -> list[Offer]:
    category_group_map = {_normalize_key(k): v for k, v in category_to_group.items()}
    inputs: list[OfferInput] = []
    skipped: list[str] = []

    for payload in scraped_offers:
        title = str(_pick(payload, ("назв", "рќр°р·", "title")) or "").strip()
        if not title:
            title = "unknown offer"
        raw_text = str(_pick(payload, ("текст", "рўрµрє", "description")) or "").strip()
        raw_formula = str(_pick(payload, ("формул", "р¤рѕсЂ", "formula")) or "").strip()

        discount = _extract_discount(raw_formula, raw_text)
        if discount is None:
            skipped.append(f"title='{title}' reason=discount not parsed")
            continue

        stay_periods = _parse_ranges(_pick(payload, ("прожив", "рїсЂрѕж", "stay")))
        if not stay_periods:
            skipped.append(f"title='{title}' reason=stay periods not parsed")
            continue

        booking_ranges = _parse_ranges(_pick(payload, ("брони", "р±сЂрѕ", "booking")))
        booking_period = booking_ranges[0] if booking_ranges else None

        raw_categories = _pick(payload, ("категор", "рєр°с‚егор", "category"))
        categories = _normalize_categories(raw_categories)
        if categories is None and _is_all_villas(raw_categories):
            categories = _expand_all_villas_categories(category_to_group)
        groups: list[str] | None = None
        if categories:
            groups = sorted(
                {
                    category_group_map.get(_normalize_key(category), "")
                    for category in categories
                }
            )
            groups = [x for x in groups if x] or None

        discount_type, discount_payload = discount
        discount_kwargs: dict[str, Any] = {}
        if discount_type == "PERCENT_OFF":
            discount_kwargs["percent"] = discount_payload["percent"]
        else:
            discount_kwargs["x"] = discount_payload["x"]
            discount_kwargs["y"] = discount_payload["y"]

        inputs.append(
            OfferInput(
                offer_id=_offer_id(title, raw_text),
                title=title,
                loyalty_compatible=bool(_pick(payload, ("лоял", "summ", "р»рѕял")) or False),
                min_nights=_parse_min_nights(_pick(payload, ("миним", "рјрёрЅ", "min")), raw_text),
                booking_period=booking_period,
                stay_periods=stay_periods,
                discount_type=discount_type,  # type: ignore[arg-type]
                allowed_groups=groups,
                allowed_categories=categories,
                raw_text=raw_text,
                raw_formula=raw_formula or None,
                **discount_kwargs,
            )
        )

    for reason in skipped:
        print(f"[warn] skipped offer: {reason}")

    if fail_fast and skipped:
        raise OffersTransformError("Offers transform skipped items:\n" + "\n".join(skipped))

    return map_offers(inputs)
