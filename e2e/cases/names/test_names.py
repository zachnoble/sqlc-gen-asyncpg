import datetime
import decimal
import importlib
import ipaddress
import typing
import uuid
from typing import Any

import asyncpg
import msgspec

from conform import check_return, conforms


def gen(variant: str, name: str) -> Any:
    return importlib.import_module(f"cases.names.{variant}.{name}")


def full_params(query: Any, models: Any) -> Any:
    return query.InsertClassParams(
        from_=1, def_="d", None_="n", True_=True, self="s", id=10, type="t", list=[1, 2],
        datetime=datetime.datetime(2020, 1, 1), decimal=decimal.Decimal("1.5"), uuid=uuid.UUID(int=5),
        typing="ty", models=models.WeirdEnum.VALUE_0, msgspec="m", asyncpg=asyncpg.Range(1, 2),
        ipaddress=ipaddress.IPv4Address("1.2.3.4"), collections=7, enum=models.WeirdEnum.BACKSLASH,
        conn="c", arg="a", args="as", _row="r", _rows="rs", _stmt="st", _out="o", _status="sta", _n="nn",
        _a="aa", _records="rec", first_name="f1", first_name_2="f2", _2fa=False, café="é", Name="N",
        name="n", _secret="sec", WeirdEnum=models.WeirdEnum.MRO, OtherWeirdEnum=models.OtherWeirdEnum.Z,
    )


def test_enum_members() -> None:
    m = gen("gen", "models")
    values = [e.value for e in m.WeirdEnum]
    assert values == ["", " ", "a-b", "a_b", "A", "a", "1st", "_x", "none", "it's", "back\\slash", "ñ", "value", "name", "mro", "VALUE_3"]
    assert m.WeirdEnum.VALUE_15.value == "VALUE_3"
    assert m.WeirdEnum.VALUE_3.value == "a_b"
    assert m.WeirdEnum.ITS.value == "it's"
    assert list(m.OtherWeirdEnum) == [m.OtherWeirdEnum.Z]


def test_class_names() -> None:
    m = gen("gen", "models")
    for name in ("Class", "UserProfile", "_1stTable", "ÜnïcodeTâble", "OtherThing", "WeirdEnum", "OtherWeirdEnum"):
        assert hasattr(m, name), name


def test_method_names() -> None:
    q = gen("gen", "query").QueryQueries
    for name in ("close_", "with_tx_", "prepare_", "import_", "get_snake_case", "list_httpurls"):
        assert callable(getattr(q, name)), name


async def test_keyword_and_shadowing_fields(conn: asyncpg.Connection) -> None:
    for variant in ("gen", "gen_prepared", "gen_dbarg"):
        db, models, query = gen(variant, "db"), gen(variant, "models"), gen(variant, "query")
        await conn.execute('DELETE FROM "class"')
        dbarg = variant == "gen_dbarg"
        q = db.Queries() if dbarg else (await db.Queries.prepare(conn) if variant == "gen_prepared" else db.Queries(conn))
        args = (conn,) if dbarg else ()
        row = await q.insert_class(*args, full_params(query, models))
        assert row is not None
        conforms(row, query.InsertClassRow)
        assert row.from_ == 1 and row.None_ == "n" and row.self == "s" and row.list == [1, 2]
        assert row.models is models.WeirdEnum.VALUE_0 and row.enum is models.WeirdEnum.BACKSLASH
        assert row.WeirdEnum is models.WeirdEnum.MRO and row.OtherWeirdEnum is models.OtherWeirdEnum.Z
        assert (row.first_name, row.first_name_2, row.café, row.Name, row.name, row._secret) == ("f1", "f2", "é", "N", "n", "sec")
        assert await q.get_class(*args, 10) == query.GetClassRow(**msgspec.structs.asdict(row))
        if variant == "gen":
            ids = await q.params_named_like_locals(
                *args, "s", "c", "r", "rs", models.WeirdEnum.VALUE_0, "ty", "st", "o", "sta", "nn", "aa", "a"
            )
        else:
            ids = await q.params_named_like_locals(
                *args,
                query.ParamsNamedLikeLocalsParams(
                    self="s", conn="c", _row="r", _rows="rs", models=models.WeirdEnum.VALUE_0, typing="ty",
                    _stmt="st", _out="o", _status="sta", _n="nn", _a="aa", arg="a",
                ),
            )
        assert ids == [10]
        assert await q.single_param_self(*args, "s") == 10
        assert await q.single_param_models(*args, models.WeirdEnum.VALUE_0) is models.WeirdEnum.VALUE_0
        assert await q.close_(*args) == 1
        assert await q.with_tx_(*args) == 2
        assert await q.prepare_(*args) == 3
        assert await q.import_(*args) == 4
        assert await q.get_snake_case(*args) == 5
        assert await q.list_httpurls(*args) == [6]
        anon = await q.anonymous_columns(*args)
        check_return(q.anonymous_columns, anon)
        assert anon == query.AnonymousColumnsRow(column_1=1, column_2="a", column_3=4, column_4=None, id=10)
        dup = await q.duplicate_columns(*args)
        assert dup == query.DuplicateColumnsRow(id=10, id_2=10, id_3=10, count=1, count_2=1)
        assert await q.repeated_named_param(*args, 10) == [10]
        assert await q.repeated_named_param(*args, 7) == [10]  # matches "collections"
        assert await q.repeated_positional(*args, 1) == [10]
        if variant == "gen":
            assert await q.unnamed_params(*args, 2, 3) == 5
        else:
            assert await q.unnamed_params(*args, query.UnnamedParamsParams(dollar_1=2, dollar_2=3)) == 5
        thing = await q.other_schema(*args, 1, models.OtherWeirdEnum.Z) if variant == "gen" else await q.other_schema(
            *args, query.OtherSchemaParams(id=1, e=models.OtherWeirdEnum.Z)
        )
        assert thing == models.OtherThing(id=1, e=models.OtherWeirdEnum.Z)
        await conn.execute("DELETE FROM other.things")
        assert await q.quoting(*args, "x") == '"""x\\\n\\'
        assert await q.get_user_profile(*args) is None


def test_annotations_resolve_everywhere() -> None:
    # fields shadowing modules/builtins/enums (PEP 649)
    for variant in ("gen", "gen_prepared", "gen_dbarg"):
        models, query = gen(variant, "models"), gen(variant, "query")
        hints = typing.get_type_hints(models.Class)
        assert hints["datetime"] == datetime.datetime | None
        assert hints["list"] == list[int] | None
        assert hints["models"] == models.WeirdEnum | None
        assert hints["asyncpg"] == asyncpg.Range[int] | None
        typing.get_type_hints(query.InsertClassParams)
        typing.get_type_hints(query.GetClassRow)


def test_json_camel_names() -> None:
    m = gen("gen_prepared", "models")
    obj = m.UserProfile(id=1)
    assert msgspec.json.encode(obj) == b'{"id":1}'


async def test_methods_shadowing_builtins_and_void(conn: asyncpg.Connection) -> None:
    for variant in ("gen", "gen_prepared"):
        db, query = gen(variant, "db"), gen(variant, "query")
        q = await db.Queries.prepare(conn) if variant == "gen_prepared" else db.Queries(conn)
        # methods shadowing builtins (PEP 649)
        for name in ("list", "int", "get_class", "list_httpurls", "lock"):
            typing.get_type_hints(getattr(query.QueryQueries, name))
        assert typing.get_type_hints(query.QueryQueries.list_httpurls)["return"] == list[int]
        assert await q.list() == []
        assert await q.int() == 0
        async with conn.transaction():
            assert await q.lock() is None  # void result
            assert await q.lock_many() == [None, None]
        assert typing.get_type_hints(query.QueryQueries.lock)["return"] is type(None)
