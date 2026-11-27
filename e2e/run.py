#!/usr/bin/env python3
"""E2E driver: build wasm, generate cases, type check, run pytest.

Usage: python3 run.py [-k CASE] [--pythons 3.13,3.14] [--no-typecheck] [-- PYTEST_ARGS]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

E2E = pathlib.Path(__file__).resolve().parent
ROOT = E2E.parent
CASES = E2E / "cases"
WASM = ROOT / "bin" / "sqlc-gen-asyncpg.wasm"
SQLC = os.environ.get("SQLC", shutil.which("sqlc") or str(pathlib.Path.home() / "go/bin/sqlc"))


def run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)  # type: ignore[call-overload,no-any-return]


def build() -> str:
    WASM.parent.mkdir(exist_ok=True)
    env = dict(os.environ, GOOS="wasip1", GOARCH="wasm")
    r = run(["go", "build", "-trimpath", "-o", str(WASM), "."], cwd=ROOT, env=env)
    if r.returncode != 0:
        sys.exit("wasm build failed:\n" + r.stderr)
    return hashlib.sha256(WASM.read_bytes()).hexdigest()


def outputs(cfg: dict[str, object]) -> list[str]:
    outs = []
    for sql in cfg.get("sql", []):  # type: ignore[attr-defined]
        for cg in sql.get("codegen", []):
            outs.append(cg["out"])
    return outs


def generate(case: pathlib.Path, sha: str) -> str | None:
    cfg = json.loads((case / "sqlc.json").read_text())
    plugins = cfg.setdefault("plugins", [])
    plugins.insert(0, {"name": "py", "wasm": {"url": WASM.as_uri(), "sha256": sha}})
    gen_cfg = case / "sqlc.generated.json"
    gen_cfg.write_text(json.dumps(cfg, indent=2) + "\n")
    for out in outputs(cfg):
        shutil.rmtree(case / out, ignore_errors=True)
    text = gen_cfg.read_text()
    if "${E2E_ANALYZER_DSN}" in text:
        gen_cfg.write_text(text.replace("${E2E_ANALYZER_DSN}", analyzer_db(case)))
    r = run([SQLC, "generate", "-f", str(gen_cfg)], cwd=case)
    expected = case / "expected_error.txt"
    if expected.exists():
        want = expected.read_text().strip()
        if r.returncode == 0:
            return f"{case.name}: expected sqlc generate to fail with {want!r}, but it succeeded"
        if want not in r.stderr:
            return f"{case.name}: expected error {want!r}, got:\n{r.stderr}"
        return None
    if r.returncode != 0:
        return f"{case.name}: sqlc generate failed:\n{r.stderr}{r.stdout}"
    for out in outputs(cfg):
        if not (case / out / "__init__.py").exists():
            return f"{case.name}: {out}/__init__.py missing"
    return None


def analyzer_db(case: pathlib.Path) -> str:
    """Create a database with the case schema for sqlc's analyzer."""
    dsn = os.environ.get("E2E_DSN", "postgresql://postgres:postgres@localhost:55439/postgres")
    base = dsn.rpartition("/")[0]
    name = f"analyzer_{case.name}"
    schema = case / "schema.sql"
    py = venv_python("3.13")
    script = (
        "import asyncio, asyncpg, sys\n"
        "async def main():\n"
        "    a = await asyncpg.connect(sys.argv[1] + '/postgres')\n"
        "    await a.execute(f'DROP DATABASE IF EXISTS \"{sys.argv[2]}\" WITH (FORCE)')\n"
        "    await a.execute(f'CREATE DATABASE \"{sys.argv[2]}\"')\n"
        "    await a.close()\n"
        "    c = await asyncpg.connect(sys.argv[1] + '/' + sys.argv[2])\n"
        "    await c.execute(open(sys.argv[3]).read())\n"
        "    await c.close()\n"
        "asyncio.run(main())\n"
    )
    r = run([str(py), "-I", "-c", script, base, name, str(schema.resolve())])
    if r.returncode != 0:
        sys.exit("analyzer database setup failed:\n" + r.stderr)
    return f"{base}/{name}"


def venv_python(version: str) -> pathlib.Path:
    venv = E2E / f".venv{version.replace('.', '')}"
    py = venv / "bin" / "python"
    if not py.exists():
        r = run(["uv", "venv", "-q", "--python", version, str(venv)])
        if r.returncode != 0:
            sys.exit(r.stderr)
        r = run(["uv", "pip", "install", "-q", "--python", str(py), "-r", str(E2E / "pyproject.toml")])
        if r.returncode != 0:
            sys.exit(r.stderr)
    return py


def checked(label: str, r: subprocess.CompletedProcess[str]) -> bool:
    out = (r.stdout + r.stderr).strip()
    print(f"{label}:", out.splitlines()[-1] if out else "ok")
    if r.returncode != 0:
        print(out)
    return r.returncode == 0


def typecheck(paths: list[str], versions: list[str]) -> bool:
    """ty and pyrefly per Python version, ruff on generated packages."""
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    ok = True
    for version in versions:
        py = venv_python(version)
        bindir = py.parent
        ok &= checked(f"ty (py{version})", run(
            [str(bindir / "ty"), "check", "--python", str(py.parent.parent), "--python-version", version,
             "--error-on-warning", "--output-format", "concise", *paths], cwd=E2E, env=env))
        ok &= checked(f"pyrefly (py{version})", run(
            [str(bindir / "pyrefly"), "check", "--python-interpreter-path", str(py), "--python-version", version,
             "--output-format", "min-text", *paths], cwd=E2E, env=env))
    bindir = venv_python(versions[0]).parent
    gens = [str(p) + "/" for p_ in paths for p in (E2E / p_).iterdir() if (p / "__init__.py").exists()]
    ok &= checked("ruff", run([str(bindir / "ruff"), "check", "--no-cache", "--ignore-noqa", "--select",
                                "F,E9,PLE,B006,B008,PLW0127", *gens], cwd=E2E))
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", default="", help="only cases whose name contains this")
    ap.add_argument("--pythons", default="3.13,3.14")
    ap.add_argument("--no-typecheck", action="store_true")
    ap.add_argument("pytest_args", nargs="*")
    args = ap.parse_args()

    sha = build()
    cases = sorted(p for p in CASES.iterdir() if (p / "sqlc.json").exists() and args.k in p.name)
    failures = [f for f in (generate(c, sha) for c in cases) if f]
    for f in failures:
        print("FAIL", f)
    if failures:
        return 1
    print(f"generated {len(cases)} cases")

    runnable = [c for c in cases if not (c / "expected_error.txt").exists()]
    if not args.no_typecheck and runnable:
        paths = [str(c.relative_to(E2E)) for c in runnable]
        if not typecheck(paths, args.pythons.split(",")):
            return 1

    tests = [str(c.relative_to(E2E)) for c in runnable if list(c.glob("test_*.py"))]
    if not tests:
        return 0
    rc = 0
    for version in args.pythons.split(","):
        py = venv_python(version)
        print(f"== pytest on Python {version}")
        r = subprocess.run([str(py), "-m", "pytest", "-q", *tests, *args.pytest_args], cwd=E2E)
        rc |= r.returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
