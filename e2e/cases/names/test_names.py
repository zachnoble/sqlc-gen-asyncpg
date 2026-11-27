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


def test_function_names() -> None:
    q = gen("gen", "query")
    for name in ("close", "with_tx", "prepare", "import_", "get_snake_case", "list_httpurls", "list_", "int_"):
        assert callable(getattr(q, name)), name
    # names the generated module itself relies on are suffixed
    assert not hasattr(q, "int") and not hasattr(q, "list") and q.typing is typing


async def test_keyword_and_shadowing_fields(conn: asyncpg.Connection) -> None:
    for variant in ("gen", "gen_json"):
        models, query = gen(variant, "models"), gen(variant, "query")
        await conn.execute('DELETE FROM "class"')
        row = await query.insert_class(conn, full_params(query, models))
        assert row is not None
        conforms(row, query.InsertClassRow)
        assert row.from_ == 1 and row.None_ == "n" and row.self == "s" and row.list == [1, 2]
        assert row.models is models.WeirdEnum.VALUE_0 and row.enum is models.WeirdEnum.BACKSLASH
        assert row.WeirdEnum is models.WeirdEnum.MRO and row.OtherWeirdEnum is models.OtherWeirdEnum.Z
        assert (row.first_name, row.first_name_2, row.café, row.Name, row.name, row._secret) == ("f1", "f2", "é", "N", "n", "sec")
        assert await query.get_class(conn, 10) == query.GetClassRow(**msgspec.structs.asdict(row))
        if variant == "gen":
            ids = await query.params_named_like_locals(
                conn, "s", "c", "r", "rs", models.WeirdEnum.VALUE_0, "ty", "st", "o", "sta", "nn", "aa", "a"
            )
        else:
            ids = await query.params_named_like_locals(
                conn,
                query.ParamsNamedLikeLocalsParams(
                    self="s", conn="c", _row="r", _rows="rs", models=models.WeirdEnum.VALUE_0, typing="ty",
                    _stmt="st", _out="o", _status="sta", _n="nn", _a="aa", arg="a",
                ),
            )
        assert ids == [10]
        assert await query.single_param_self(conn, "s") == 10
        assert await query.single_param_models(conn, models.WeirdEnum.VALUE_0) is models.WeirdEnum.VALUE_0
        assert await query.close(conn) == 1
        assert await query.with_tx(conn) == 2
        assert await query.prepare(conn) == 3
        assert await query.import_(conn) == 4
        assert await query.get_snake_case(conn) == 5
        assert await query.list_httpurls(conn) == [6]
        anon = await query.anonymous_columns(conn)
        check_return(query.anonymous_columns, anon)
        assert anon == query.AnonymousColumnsRow(column_1=1, column_2="a", column_3=4, column_4=None, id=10)
        dup = await query.duplicate_columns(conn)
        assert dup == query.DuplicateColumnsRow(id=10, id_2=10, id_3=10, count=1, count_2=1)
        assert await query.repeated_named_param(conn, 10) == [10]
        assert await query.repeated_named_param(conn, 7) == [10]  # matches "collections"
        assert await query.repeated_positional(conn, 1) == [10]
        if variant == "gen":
            assert await query.unnamed_params(conn, 2, 3) == 5
        else:
            assert await query.unnamed_params(conn, query.UnnamedParamsParams(dollar_1=2, dollar_2=3)) == 5
        thing = await query.other_schema(conn, 1, models.OtherWeirdEnum.Z) if variant == "gen" else await query.other_schema(
            conn, query.OtherSchemaParams(id=1, e=models.OtherWeirdEnum.Z)
        )
        assert thing == models.OtherThing(id=1, e=models.OtherWeirdEnum.Z)
        await conn.execute("DELETE FROM other.things")
        assert await query.quoting(conn, "x") == '"""x\\\n\\'
        assert await query.get_user_profile(conn) is None


def test_annotations_resolve_everywhere() -> None:
    # fields shadowing modules/builtins/enums (PEP 649)
    for variant in ("gen", "gen_json"):
        models, query = gen(variant, "models"), gen(variant, "query")
        hints = typing.get_type_hints(models.Class)
        assert hints["datetime"] == datetime.datetime | None
        assert hints["list"] == list[int] | None
        assert hints["models"] == models.WeirdEnum | None
        assert hints["asyncpg"] == asyncpg.Range[int] | None
        typing.get_type_hints(query.InsertClassParams)
        typing.get_type_hints(query.GetClassRow)
        typing.get_type_hints(query.params_named_like_locals)


def test_json_camel_names() -> None:
    m = gen("gen_json", "models")
    obj = m.UserProfile(id=1)
    assert msgspec.json.encode(obj) == b'{"id":1}'


async def test_functions_named_like_builtins_and_void(conn: asyncpg.Connection) -> None:
    query = gen("gen", "query")
    for name in ("list_", "int_", "get_class", "list_httpurls", "lock"):
        typing.get_type_hints(getattr(query, name))
    assert typing.get_type_hints(query.list_httpurls)["return"] == list[int]
    assert await query.list_(conn) == []
    assert await query.int_(conn) == 0
    async with conn.transaction():
        assert await query.lock(conn) is None  # void result
        assert await query.lock_many(conn) == [None, None]
    assert typing.get_type_hints(query.lock)["return"] is type(None)
