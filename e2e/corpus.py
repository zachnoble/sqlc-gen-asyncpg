#!/usr/bin/env python3
"""Run the plugin over sqlc's PostgreSQL endtoend corpus: generate, type check,
PREPARE every statement.

Usage: python3 corpus.py [--sqlc-src DIR] [-k FILTER]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

E2E = pathlib.Path(__file__).resolve().parent
ROOT = E2E.parent
WORK = E2E / ".corpus"
WASM = ROOT / "bin" / "sqlc-gen-asyncpg.wasm"
SQLC = os.environ.get("SQLC", shutil.which("sqlc") or str(pathlib.Path.home() / "go/bin/sqlc"))
sys.path.insert(0, str(E2E))
from run import venv_python  # noqa: E402  (creates the uv venvs on demand)

PY = venv_python("3.13")

KEEP = {
    "emit_interface", "emit_json_tags", "json_tags_id_uppercase", "json_tags_case_style", "emit_prepared_queries",
    "emit_exact_table_names", "emit_empty_slices", "emit_exported_queries", "emit_methods_with_db_argument",
    "emit_enum_valid_method", "emit_all_enum_values", "emit_sql_as_comment", "rename", "output_batch_file_name",
    "output_db_file_name", "output_models_file_name", "output_querier_file_name", "output_copyfrom_file_name",
    "output_files_suffix", "inflection_exclude_table_names", "wrap_errors", "query_parameter_limit",
    "omit_sqlc_version", "omit_unused_structs", "initialisms",
}


def py_file(name: str | None) -> str | None:
    if not name:
        return None
    stem = name.removesuffix(".go").removesuffix(".py").replace(".", "_")
    return stem + ".py"


def convert_opts(go: dict) -> dict:
    out = {k: v for k, v in go.items() if k in KEEP}
    for k in ("output_batch_file_name", "output_db_file_name", "output_models_file_name",
              "output_querier_file_name", "output_copyfrom_file_name"):
        if k in out:
            out[k] = py_file(out[k])
    if "output_files_suffix" in out:
        out["output_files_suffix"] = "".join(c if c.isalnum() or c == "_" else "_" for c in out["output_files_suffix"].removesuffix(".go"))
    if out.get("emit_methods_with_db_argument") and out.get("emit_prepared_queries"):
        out.pop("emit_prepared_queries")
    return out


def load_config(case: pathlib.Path) -> dict | None:
    for name in ("sqlc.json", "sqlc.yaml", "sqlc.yml"):
        p = case / name
        if p.exists():
            if name.endswith(".json"):
                return json.loads(p.read_text())
            r = subprocess.run([str(PY), "-I", "-c", "import json,sys,yaml;print(json.dumps(yaml.safe_load(open(sys.argv[1]))))", str(p)], capture_output=True, text=True)
            if r.returncode != 0:
                return None
            return json.loads(r.stdout)
    return None


def convert(cfg: dict) -> dict | None:
    sqls = []
    if cfg.get("version") == "1" or "packages" in cfg:
        for i, pkg in enumerate(cfg.get("packages", [])):
            if pkg.get("engine", "postgresql") != "postgresql":
                continue
            go = {k: v for k, v in pkg.items() if k not in ("path", "engine", "schema", "queries", "name", "sql_package")}
            sqls.append({"engine": "postgresql", "schema": pkg["schema"], "queries": pkg["queries"],
                         "codegen": [{"plugin": "py", "out": f"py{i}", "options": convert_opts(go)}]})
    else:
        for i, sql in enumerate(cfg.get("sql", [])):
            if sql.get("engine") != "postgresql":
                continue
            go = (sql.get("gen") or {}).get("go")
            if go is None:
                continue
            entry = {k: v for k, v in sql.items() if k in ("engine", "schema", "queries", "strict_function_checks", "strict_order_by")}
            entry["codegen"] = [{"plugin": "py", "out": f"py{i}", "options": convert_opts(go)}]
            sqls.append(entry)
    if not sqls:
        return None
    return {"version": "2", "sql": sqls}


DSN = os.environ.get("E2E_DSN", "postgresql://postgres:postgres@localhost:55439/postgres")
SETUP = """
import asyncio, asyncpg, pathlib, sys
async def main():
    base, name, case, *schema = sys.argv[1:]
    a = await asyncpg.connect(base + "/postgres")
    await a.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await a.execute(f'CREATE DATABASE "{name}"')
    await a.close()
    c = await asyncpg.connect(base + "/" + name)
    for spec in schema:
        p = pathlib.Path(case) / spec
        files = sorted(x for x in p.iterdir() if x.suffix == ".sql") if p.is_dir() else [p]
        for f in files:
            text = f.read_text().split("-- +goose Down")[0].split("-- migrate:down")[0]
            body = "\\n".join(l for l in text.splitlines() if not l.strip().startswith("--")).strip()
            if body:
                await c.execute(text)
    await c.close()
asyncio.run(main())
"""


def analyzer_db(name: str, case: pathlib.Path, schema: str | list[str]) -> str:
    base = DSN.rpartition("/")[0]
    specs = [schema] if isinstance(schema, str) else schema
    subprocess.run([str(PY), "-I", "-c", SETUP, base, name, str(case), *specs], check=True)
    return f"{base}/{name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlc-src", default="/tmp/sqlc-src")
    ap.add_argument("-k", default="")
    args = ap.parse_args()
    testdata = pathlib.Path(args.sqlc_src) / "internal" / "endtoend" / "testdata"
    if not testdata.exists():
        sys.exit(f"sqlc source not found at {args.sqlc_src}; clone github.com/sqlc-dev/sqlc there")

    env = dict(os.environ, GOOS="wasip1", GOARCH="wasm")
    subprocess.run(["go", "build", "-trimpath", "-o", str(WASM), "."], cwd=ROOT, env=env, check=True)
    sha = hashlib.sha256(WASM.read_bytes()).hexdigest()

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir()
    tree = WORK / "testdata"
    shutil.copytree(testdata, tree, ignore=shutil.ignore_patterns("go", "*.go", "stderr*"))
    cases = []
    for cfg_path in sorted(testdata.rglob("sqlc.*")):
        case = cfg_path.parent
        rel = case.relative_to(testdata)
        if args.k not in str(rel):
            continue
        if any(case.glob("stderr*.txt")) or (case / "stderr").exists():
            continue
        cfg = load_config(case)
        if cfg is None:
            continue
        conv = convert(cfg)
        if conv is None:
            continue
        name = "c_" + "".join(ch if ch.isalnum() else "_" for ch in str(rel))
        dst = tree / rel
        exec_json = case / "exec.json"
        if exec_json.exists() and "managed-db" in exec_json.read_text():
            # sqlc runs these against a managed database; use the analyzer.
            for i, entry in enumerate(conv["sql"]):
                entry["database"] = {"uri": analyzer_db(f"an_{len(cases)}_{i}", dst, entry["schema"])}
                entry["analyzer"] = {"database": True}
        conv["plugins"] = [{"name": "py", "wasm": {"url": WASM.as_uri(), "sha256": sha}}]
        (dst / "sqlc.py.json").write_text(json.dumps(conv, indent=2))
        cases.append((name, dst, conv))

    def generate(case: tuple[str, pathlib.Path, dict]) -> subprocess.CompletedProcess[str]:
        return subprocess.run([SQLC, "generate", "-f", "sqlc.py.json"], cwd=case[1], capture_output=True, text=True)

    # Each case is independent; sqlc generate is dominated by wasm startup, so fan out.
    # Run the first case alone so sqlc's plugin cache is populated before concurrent use.
    results = [generate(cases[0])] if cases else []
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        results += pool.map(generate, cases[1:])
    gen_fail, ok = [], []
    for (name, dst, conv), r in zip(cases, results):
        if r.returncode != 0:
            gen_fail.append((name, r.stderr.strip()))
        else:
            ok.append((name, dst, conv))
    print(f"corpus: {len(cases)} postgresql cases, {len(ok)} generated, {len(gen_fail)} failed to generate")
    for name, err in gen_fail:
        print(f"  GENERATE FAIL {name}: {err[:400]}")

    compile_fail = []
    for name, dst, _ in ok:
        for f in dst.rglob("py*/*.py"):
            try:
                ast.parse(f.read_text(), str(f))
            except SyntaxError as e:
                compile_fail.append(f"{f}: {e}")
    for c in compile_fail:
        print("  SYNTAX", c)

    pkgs = WORK / "pkgs"
    pkgs.mkdir()
    for name, dst, conv in ok:
        for s_ in conv["sql"]:
            for cg in s_["codegen"]:
                shutil.copytree(dst / cg["out"], pkgs / f"{name}_{cg['out']}")
    (pkgs / "pyproject.toml").write_text(
        '[tool.ty.rules]\nall = "error"\n\n[tool.pyrefly]\npreset = "strict"\nsearch-path = ["."]\nuse-ignore-files = false\n'
    )
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    type_ok = True
    for version in ("3.13", "3.14"):
        py = venv_python(version)
        r = subprocess.run([str(py.parent / "ty"), "check", "--python", str(py.parent.parent), "--python-version", version,
                            "--error-on-warning", "--output-format", "concise", "."], cwd=pkgs, capture_output=True, text=True, env=env)
        out = (r.stdout + r.stderr).strip()
        print(f"ty (py{version}):", out.splitlines()[-1] if out else "ok")
        if r.returncode != 0:
            print(out[-20000:])
            type_ok = False
        r = subprocess.run([str(py.parent / "pyrefly"), "check", "--python-interpreter-path", str(py), "--python-version", version,
                            "--output-format", "min-text", "."], cwd=pkgs, capture_output=True, text=True, env=env)
        out = (r.stdout + r.stderr).strip()
        print(f"pyrefly (py{version}):", out.splitlines()[-1] if out else "ok")
        if r.returncode != 0:
            print(out[-20000:])
            type_ok = False

    r2 = subprocess.run([str(PY), str(E2E / "corpus_prepare.py"), *[f"{name}={d}" for name, d, _ in ok]], cwd=E2E)
    failed = bool(gen_fail or compile_fail or not type_ok or r2.returncode)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
