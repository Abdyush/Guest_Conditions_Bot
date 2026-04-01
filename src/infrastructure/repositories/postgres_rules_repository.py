from __future__ import annotations

import csv
import os
from io import StringIO
from pathlib import Path

from sqlalchemy import INTEGER, TEXT, Column, MetaData, Table, create_engine, select, text
from sqlalchemy.engine import Engine, URL, make_url

from src.application.ports.rules_repository import RulesRepository
from src.domain.services.child_supplement_policy import ChildSupplementPolicy
from src.domain.value_objects.category_rule import CategoryRule, PricingMode
from src.infrastructure.loaders.category_rules_loader import parse_child_supplement_policy


metadata = MetaData()

rules_table = Table(
    "category_rules",
    metadata,
    Column("category_name", TEXT, primary_key=True),
    Column("group_id", TEXT, nullable=False),
    Column("capacity_adults", INTEGER, nullable=False),
    Column("free_infants", INTEGER, nullable=False),
    Column("pricing_mode", TEXT, nullable=False),
    Column("payment_4_13", TEXT, nullable=True),
)


def _csv_reader(path: Path) -> csv.DictReader:
    raw = path.read_bytes()
    try:
        text_value = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_value = raw.decode("cp1251")
    return csv.DictReader(StringIO(text_value))


def _parse_int(raw: str | None, *, default: int = 0) -> int:
    value = (raw or "").strip().replace(" ", "")
    value = value.replace("\u2014", "-").replace("\u2013", "-")
    if not value or value == "-":
        return default
    return int(value)


def _parse_pricing_mode(raw: str | None) -> PricingMode:
    value = (raw or "").strip().upper()
    if value in {"PER_ADULT", "PER-ADULT", "PER ADULT"} or "ADULT" in value or "\u0412\u0417\u0420\u041e\u0421" in value:
        return PricingMode.PER_ADULT
    return PricingMode.FLAT


def _clean_database_url(raw: str) -> str:
    cleaned = raw.strip().strip("'\"").replace("\ufeff", "")
    for bad in ("\u00a0", "\u200b", "\u200c", "\u200d", "\u2060", "\u2018", "\u2019", "\u201c", "\u201d"):
        cleaned = cleaned.replace(bad, "")
    return cleaned


def _resolve_database_url(database_url: str | None) -> URL:
    raw_url = database_url or os.getenv("DATABASE_URL")
    if raw_url:
        return make_url(_clean_database_url(raw_url))

    db_name = _clean_database_url(os.getenv("POSTGRES_DB") or "")
    user = _clean_database_url(os.getenv("POSTGRES_USER") or "")
    password_raw = os.getenv("POSTGRES_PASSWORD")
    password = _clean_database_url(password_raw) if password_raw is not None else None
    host = _clean_database_url(os.getenv("POSTGRES_HOST") or "localhost")
    port_raw = _clean_database_url(os.getenv("POSTGRES_PORT") or "5432")
    if not db_name or not user or password is None:
        raise ValueError("DATABASE_URL or POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD is required")
    return URL.create(
        drivername="postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=int(port_raw),
        database=db_name,
    )


class PostgresRulesRepository(RulesRepository):
    def __init__(self, database_url: str | None = None):
        url = _resolve_database_url(database_url)
        self._engine = create_engine(url, future=True)
        self._init_schema(self._engine)

    @staticmethod
    def _init_schema(engine: Engine) -> None:
        metadata.create_all(engine)

    def replace_from_csv(self, rules_csv_path: str | Path) -> None:
        rows = []
        for row in _csv_reader(Path(rules_csv_path)):
            category_name = (row.get("\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f") or "").strip()
            group_id = (row.get("\u0413\u0440\u0443\u043f\u043f\u0430") or "").strip()
            if not category_name or not group_id:
                continue
            pricing_mode = _parse_pricing_mode(row.get("PricingMode"))
            rows.append(
                {
                    "category_name": category_name,
                    "group_id": group_id,
                    "capacity_adults": _parse_int(row.get("\u0412\u043c\u0435\u0441\u0442\u0438\u043c\u043e\u0441\u0442\u044c_\u0432\u0437\u0440\u043e\u0441\u043b\u044b\u0435"), default=1),
                    "free_infants": _parse_int(row.get("FreeInfants"), default=0),
                    "pricing_mode": pricing_mode.value,
                    "payment_4_13": (row.get("\u041e\u043f\u043b\u0430\u0442\u0430_4_13") or "").strip() or None,
                }
            )

        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE category_rules"))
            if rows:
                conn.execute(rules_table.insert(), rows)

    def get_category_to_group(self) -> dict[str, str]:
        stmt = select(rules_table.c.category_name, rules_table.c.group_id)
        out: dict[str, str] = {}
        with self._engine.connect() as conn:
            for row in conn.execute(stmt):
                out[row.category_name] = row.group_id
        return out

    def get_group_rules(self) -> dict[str, CategoryRule]:
        stmt = select(
            rules_table.c.group_id,
            rules_table.c.capacity_adults,
            rules_table.c.free_infants,
            rules_table.c.pricing_mode,
        )
        out: dict[str, CategoryRule] = {}
        with self._engine.connect() as conn:
            for row in conn.execute(stmt):
                group_id = row.group_id
                if group_id in out:
                    continue
                out[group_id] = CategoryRule(
                    group_id=group_id,
                    capacity_adults=int(row.capacity_adults),
                    free_infants=int(row.free_infants),
                    pricing_mode=PricingMode(row.pricing_mode),
                )
        return out

    def get_child_policies(self) -> dict[str, ChildSupplementPolicy]:
        stmt = select(rules_table.c.group_id, rules_table.c.pricing_mode, rules_table.c.payment_4_13)
        out: dict[str, ChildSupplementPolicy] = {}
        with self._engine.connect() as conn:
            for row in conn.execute(stmt):
                group_id = row.group_id
                if group_id in out:
                    continue
                mode = PricingMode(row.pricing_mode)
                out[group_id] = parse_child_supplement_policy(row.payment_4_13, pricing_mode=mode)
        return out
