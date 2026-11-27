"""Fixtures. Each test gets a fresh database cloned from a per-case template."""

from __future__ import annotations

import itertools
import os
import pathlib
from collections.abc import AsyncIterator

import asyncpg
import pytest

ROOT = pathlib.Path(__file__).parent
DSN = os.environ.get("E2E_DSN", "postgresql://postgres:postgres@localhost:55439/postgres")
_counter = itertools.count()
_templates: dict[str, str] = {}


def _dsn_for(db: str) -> str:
    base, _, _ = DSN.rpartition("/")
    return f"{base}/{db}"


def schema_sql(case_dir: pathlib.Path) -> str:
    single = case_dir / "schema.sql"
    if single.exists():
        return single.read_text()
    d = case_dir / "schema"
    return "\n;\n".join(p.read_text() for p in sorted(d.glob("*.sql")))


async def _template_for(case_dir: pathlib.Path) -> str:
    name = "tmpl_" + case_dir.name + "_" + str(os.getpid())
    if name in _templates:
        return name
    admin = await asyncpg.connect(DSN)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(_dsn_for(name))
    try:
        await conn.execute(schema_sql(case_dir))
    finally:
        await conn.close()
    _templates[name] = name
    return name


@pytest.fixture
async def dsn(request: pytest.FixtureRequest) -> AsyncIterator[str]:
    case_dir = pathlib.Path(request.path).parent
    tmpl = await _template_for(case_dir)
    name = f"t_{case_dir.name}_{os.getpid()}_{next(_counter)}"
    admin = await asyncpg.connect(DSN)
    try:
        await admin.execute(f'CREATE DATABASE "{name}" TEMPLATE "{tmpl}"')
    finally:
        await admin.close()
    try:
        yield _dsn_for(name)
    finally:
        admin = await asyncpg.connect(DSN)
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        finally:
            await admin.close()


@pytest.fixture
async def conn(dsn: str) -> AsyncIterator[asyncpg.Connection]:
    c = await asyncpg.connect(dsn)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
async def pool(dsn: str) -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        yield p
    finally:
        await p.close()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    import asyncio

    async def drop() -> None:
        if not _templates:
            return
        admin = await asyncpg.connect(DSN)
        try:
            for name in _templates:
                await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        finally:
            await admin.close()

    try:
        asyncio.run(drop())
    except Exception:
        pass
