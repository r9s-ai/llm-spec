#!/usr/bin/env python3
"""Migrate llm-spec.toml + suites-registry/providers/*.json5 into web DB tables."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from llm_spec_web.core.db import Base
from llm_spec_web.models import ProviderConfigModel, Suite, SuiteVersion
from llm_spec_web.services.suite_service import SuiteService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate suites/provider config into web DB")
    parser.add_argument(
        "--database-url",
        default="postgresql+psycopg://postgres:postgres@localhost:5432/llm_spec",
        help="SQLAlchemy database URL",
    )
    parser.add_argument("--config", default="llm-spec.toml", help="Path to llm-spec.toml")
    parser.add_argument(
        "--suites",
        default="suites-registry/providers",
        help="Suites directory",
    )
    parser.add_argument("--created-by", default="migration", help="Audit value for created_by")
    return parser.parse_args()


def migrate_provider_configs(db: Session, config_path: Path) -> None:
    if not config_path.exists():
        print(f"[skip] config not found: {config_path}")
        return

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    known_sections = {"log", "report"}
    for key, value in data.items():
        if key in known_sections or not isinstance(value, dict):
            continue
        if "base_url" not in value or "api_key" not in value:
            continue

        row = db.get(ProviderConfigModel, key)
        if row is None:
            row = ProviderConfigModel(
                provider=key,
                base_url=str(value["base_url"]),
                timeout=float(value.get("timeout", 30.0)),
                api_key=str(value["api_key"]),
                extra_config={},
            )
            db.add(row)
            print(f"[create] provider_config {key}")
        else:
            row.base_url = str(value["base_url"])
            row.timeout = float(value.get("timeout", 30.0))
            row.api_key = str(value["api_key"])
            db.add(row)
            print(f"[update] provider_config {key}")
    db.commit()


def latest_version(db: Session, suite_id: str) -> SuiteVersion | None:
    stmt = (
        select(SuiteVersion)
        .where(SuiteVersion.suite_id == suite_id)
        .order_by(SuiteVersion.version.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def migrate_suites(db: Session, suites_dir: Path, created_by: str) -> None:
    service = SuiteService()

    for suite_path in sorted(suites_dir.rglob("*.json5")):
        raw = suite_path.read_text(encoding="utf-8")
        provider, endpoint = _extract_provider_endpoint(raw, suite_path)
        if provider is None or endpoint is None:
            continue

        suite = db.execute(
            select(Suite).where(Suite.provider == provider, Suite.endpoint == endpoint)
        ).scalar_one_or_none()

        if suite is None:
            suite = service.create_suite(
                db,
                provider=provider,
                endpoint=endpoint,
                name=f"{provider} {endpoint}",
                raw_json5=raw,
                created_by=created_by,
            )
            print(f"[create] suite {suite_path} -> {suite.id}")
            continue

        lv = latest_version(db, suite.id)
        if lv and lv.raw_json5 == raw:
            print(f"[skip] unchanged {suite_path}")
            continue

        sv = service.create_version(db, suite_id=suite.id, raw_json5=raw, created_by=created_by)
        print(f"[version] {suite_path} -> v{sv.version}")


def _extract_provider_endpoint(raw_json5: str, path: Path) -> tuple[str | None, str | None]:
    import json5

    try:
        data = json5.loads(raw_json5)
    except Exception as exc:
        print(f"[error] parse {path}: {exc}")
        return None, None

    if not isinstance(data, dict):
        print(f"[error] expected object in suite file: {path}")
        return None, None

    provider = data.get("provider")
    endpoint = data.get("endpoint")
    if not isinstance(provider, str) or not isinstance(endpoint, str):
        print(f"[error] missing provider/endpoint: {path}")
        return None, None
    return provider, endpoint


def main() -> int:
    args = parse_args()

    engine = create_engine(args.database_url, future=True)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        migrate_provider_configs(db, Path(args.config))
        migrate_suites(db, Path(args.suites), args.created_by)

    print("[done] migration finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
