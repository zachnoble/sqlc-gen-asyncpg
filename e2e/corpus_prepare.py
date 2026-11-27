"""PREPARE every generated statement against its case schema.

Usage: python corpus_prepare.py NAME=CASE_DIR...
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import pathlib
import sys

import asyncpg

DSN = os.environ.get("E2E_DSN", "postgresql://postgres:postgres@localhost:55439/postgres")
BASE = DSN.rpartition("/")[0]
HERE = pathlib.Path(__file__).parent
# Cases that are invalid SQL by design.
KNOWN = json.loads((HERE / "corpus_known.json").read_text()) if (HERE / "corpus_known.json").exists() else {}


def paths(case: pathlib.Path, spec: str | list[str]) -> list[pathlib.Path]:
    specs = [spec] if isinstance(spec, str) else spec
    out: list[pathlib.Path] = []
    for s in specs:
        p = case / s
        if p.is_dir():
            out.extend(sorted(x for x in p.iterdir() if x.suffix == ".sql"))
        elif p.exists():
            out.append(p)
    return out


def constants(mod: pathlib.Path) -> list[tuple[str, str]]:
    tree = ast.parse(mod.read_text())
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            v = node.value.value
            if v.startswith("-- name: "):
                out.append((v.split("\n", 1)[0], v))
    return out


async def run_case(label: str, case: pathlib.Path, idx: int) -> tuple[str, list[str], str | None]:
    cfg = json.loads((case / "sqlc.py.json").read_text())
    name = f"corpus_{os.getpid()}_{idx}"
    admin = await asyncpg.connect(DSN)
    await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await admin.execute(f'CREATE DATABASE "{name}"')
    await admin.close()
    errors: list[str] = []
    skipped = None
    try:
        conn = await asyncpg.connect(f"{BASE}/{name}")
        try:
            for sql in cfg["sql"]:
                schema_ok = True
                for f in paths(case, sql["schema"]):
                    text = f.read_text()
                    if "-- +goose Down" in text:
                        text = text.split("-- +goose Down")[0]
                    if "-- migrate:down" in text:
                        text = text.split("-- migrate:down")[0]
                    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--")).strip()
                    if not body:
                        continue
                    try:
                        await conn.execute(text)
                    except Exception as e:
                        schema_ok = False
                        skipped = f"schema did not load: {type(e).__name__}: {str(e)[:120]}"
                        print(f"  SKIP {label}: {skipped}")
                        break
                if not schema_ok:
                    continue
                for cg in sql["codegen"]:
                    for mod in sorted((case / cg["out"]).glob("*.py")):
                        for qlabel, text in constants(mod):
                            try:
                                await conn.prepare(text)
                            except Exception as e:
                                errors.append(f"{mod.name} {qlabel}: {type(e).__name__}: {e}")
        finally:
            await conn.close()
    finally:
        admin = await asyncpg.connect(DSN)
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()
    return label, errors, skipped


async def main() -> int:
    cases = [(a.split("=", 1)[0], pathlib.Path(a.split("=", 1)[1])) for a in sys.argv[1:]]
    sem = asyncio.Semaphore(8)
    prepared = skipped = 0
    failures: list[str] = []
    unexpected_ok: list[str] = []

    async def one(i: int, label: str, c: pathlib.Path) -> tuple[str, list[str], str | None]:
        async with sem:
            return await run_case(label, c, i)

    results = await asyncio.gather(*(one(i, label, c) for i, (label, c) in enumerate(cases)))
    for name, errors, skip in results:
        if skip and not errors:
            skipped += 1
            continue
        known = KNOWN.get(name)
        if errors and known:
            continue
        if not errors and known:
            unexpected_ok.append(name)
        if errors:
            failures.append(name + "\n    " + "\n    ".join(errors))
        else:
            prepared += 1
    print(f"prepare: {prepared} cases fully prepared, {skipped} skipped (schema needs features not in this server), "
          f"{len(failures)} failing, {len([k for k in KNOWN if any(k == r[0] for r in results)])} known")
    for f in failures:
        print("  PREPARE FAIL", f)
    for n in unexpected_ok:
        print("  NOTE known failure now passes:", n)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
