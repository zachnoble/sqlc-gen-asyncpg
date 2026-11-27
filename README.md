# sqlc-gen-asyncpg

[sqlc](https://sqlc.dev) plugin (WebAssembly) generating Python for PostgreSQL,
[asyncpg](https://github.com/MagicStack/asyncpg) and
[msgspec](https://github.com/jcrist/msgspec). Requires Python 3.13+.

## Usage

```sh
just wasm   # builds bin/sqlc-gen-asyncpg.wasm, prints sha256
```

```yaml
version: "2"
plugins:
  - name: py
    wasm:
      url: file:///path/to/sqlc-gen-asyncpg.wasm
      sha256: <sha256>
sql:
  - engine: postgresql
    schema: schema.sql
    queries: query.sql
    codegen:
      - plugin: py
        out: app/db
        options:
          emit_interface: true
```

```python
from app.db import db, query

q = db.Queries(pool)  # asyncpg.Pool or Connection
author = await q.create_author(query.CreateAuthorParams(name="Ann", bio=None))
async with pool.acquire() as conn, conn.transaction():
    await q.with_tx(conn).delete_author(author.id)
```

## Output

| file | contents |
|---|---|
| `models.py` | `StrEnum`s, one `msgspec.Struct` per table/view |
| `<query file>.py` | SQL constants, `Params`/`Row` structs, query methods |
| `batch.py`, `copyfrom.py` | `:batch*` and `:copyfrom` queries |
| `db.py` | `DBTX` protocol, `Queries` |
| `querier.py` | `Querier` protocol (`emit_interface`) |

## Commands

| command | returns |
|---|---|
| `:one` | `Row \| None` |
| `:many` | `list[Row]` |
| `:exec` | `None` |
| `:execrows` | `int` |
| `:execresult` | `str` (command status) |
| `:copyfrom` | `int` |
| `:batchexec` | `None` (`executemany`, atomic) |
| `:batchone` | `list[Row \| None]` (one transaction) |
| `:batchmany` | `list[list[Row]]` (one transaction) |

`:execlastid` emits only the SQL constant, as sqlc's pgx output does.
`sqlc.arg`, `sqlc.narg`, `sqlc.embed` and `sqlc.slice` are supported;
`IN (sqlc.slice(x))` is rewritten to `= ANY($n)`.

## Types

Annotations match asyncpg's default codecs.

| PostgreSQL | Python |
|---|---|
| integer types, `oid`, `xid` | `int` |
| `real`, `double precision` | `float` |
| `numeric` | `decimal.Decimal` |
| `boolean` | `bool` |
| `text`, `varchar`, `json`, `jsonb`, `money`, `citext`, `hstore`, `ltree`, `xml`, `tsvector`, `macaddr`, `vector`, ... | `str` |
| `bytea` | `bytes` |
| `date`, `time`, `timestamp[tz]`, `interval` | `datetime.*` |
| `uuid` | `uuid.UUID` |
| `inet`, `cidr` | `ipaddress.*` |
| ranges, multiranges | `asyncpg.Range[T]`, `list[asyncpg.Range[T]]` |
| `bit`, geometric types | `asyncpg.BitString`, `asyncpg.Point`, ... |
| enums | generated `StrEnum` |
| arrays | `list[T]` |
| domains, composites, unknown | `typing.Any` |

Nullable columns are `T | None`.

## Options

Same names and semantics as sqlc's Go generator:
`emit_interface`, `emit_methods_with_db_argument`, `emit_prepared_queries`,
`emit_exported_queries`, `emit_json_tags`, `json_tags_case_style`,
`json_tags_id_uppercase`, `emit_enum_valid_method`, `emit_all_enum_values`,
`emit_sql_as_comment`, `emit_exact_table_names`, `emit_empty_slices` (no-op),
`inflection_exclude_table_names`, `rename`, `initialisms` (default `[]`),
`query_parameter_limit`, `wrap_errors` (adds an exception note),
`omit_sqlc_version`, `omit_unused_structs`, `output_*_file_name`,
`output_files_suffix`, `overrides`.

Go-only options are rejected. Additional:

- `msgspec_struct_options`: struct keywords, e.g. `{frozen: true}`.

Overrides use `py_type` instead of `go_type`:

```yaml
overrides:
  - db_type: jsonb
    py_type: "dict[str, typing.Any]"
  - column: users.email
    py_type: {import: myapp.types, type: Email}
```

Overrides change annotations only; register an asyncpg codec if the runtime
value must change.

## Notes

- `:copyfrom` uses binary COPY, falling back to `executemany` for types asyncpg
  can't encode in binary (`money`, `citext`, `hstore`, `vector`, ...).
- `sqlc.embed` under a LEFT JOIN yields a model with `None` fields; sqlc
  doesn't report that nullability.
- Array elements are typed non-optional, as in sqlc's Go output.
- msgspec can't decode `ipaddress` unions or asyncpg types; override them to
  `str` if needed.

## Development

```sh
just check    # tidy, vet, golangci-lint, govulncheck, modernize, build, test
just e2e      # generate, ty + pyrefly, pytest on 3.13 and 3.14 (Docker, sqlc, uv)
just corpus   # sqlc's PostgreSQL endtoend corpus
just test     # everything
```

Generated code in `e2e/cases` is committed; CI fails if it is stale.
