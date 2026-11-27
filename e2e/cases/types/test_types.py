import datetime
import decimal
import ipaddress
import typing
import uuid
from typing import Any

import asyncpg
import msgspec
import pytest

from cases.types.gen import db, models, query
from conform import check_return, conforms

UTC = datetime.timezone.utc
TZ2 = datetime.timezone(datetime.timedelta(hours=2))
R = asyncpg.Range


# column -> (sent, expected)
SAMPLES: dict[str, tuple[Any, Any]] = {
    "i2": (-32768, -32768),
    "i4": (2**31 - 1, 2**31 - 1),
    "i8": (-(2**63), -(2**63)),
    "f4": (1.5, 1.5),
    "f8": (-2.25e300, -2.25e300),
    "num": (decimal.Decimal("123456789012345678901234567890.123456789"), decimal.Decimal("123456789012345678901234567890.123456789")),
    "num_p": (decimal.Decimal("1.5"), decimal.Decimal("1.500")),
    "money_": ("12.34", "$12.34"),
    "b": (False, False),
    "t": ("héllo 'quoted' \"double\" \\ \n\t 🎉", "héllo 'quoted' \"double\" \\ \n\t 🎉"),
    "vc": ("abc", "abc"),
    "ch": ("a", "a  "),
    "ci": ("MiXeD", "MiXeD"),
    "nm": ("ident", "ident"),
    "by": (b"\x00\x01\xff", b"\x00\x01\xff"),
    "d": (datetime.date(1999, 12, 31), datetime.date(1999, 12, 31)),
    "tm": (datetime.time(23, 59, 59, 999999), datetime.time(23, 59, 59, 999999)),
    "tmtz": (datetime.time(1, 2, 3, tzinfo=TZ2), datetime.time(1, 2, 3, tzinfo=TZ2)),
    "ts": (datetime.datetime(2020, 2, 29, 12, 0, 1), datetime.datetime(2020, 2, 29, 12, 0, 1)),
    "tstz": (datetime.datetime(2020, 2, 29, 12, 0, 1, tzinfo=TZ2), datetime.datetime(2020, 2, 29, 10, 0, 1, tzinfo=UTC)),
    "iv": (datetime.timedelta(days=3, seconds=5, microseconds=7), datetime.timedelta(days=3, seconds=5, microseconds=7)),
    "u": (uuid.UUID("12345678-1234-5678-1234-567812345678"), uuid.UUID("12345678-1234-5678-1234-567812345678")),
    "inet_": (ipaddress.IPv6Address("::1"), ipaddress.IPv6Address("::1")),
    "cidr_": (ipaddress.IPv4Network("10.0.0.0/8"), ipaddress.IPv4Network("10.0.0.0/8")),
    "mac": ("08:00:2b:01:02:03", "08:00:2b:01:02:03"),
    "mac8": ("08:00:2b:01:02:03:04:05", "08:00:2b:01:02:03:04:05"),
    "js": ('{"a": [1, 2]}', '{"a": [1, 2]}'),
    "jsb": ('{"b":1,"a":2}', '{"a": 2, "b": 1}'),
    "jp": ("$.a[*]", '$."a"[*]'),
    "x": ("<a>b</a>", "<a>b</a>"),
    "tsv": ("a fat cat", "'a' 'cat' 'fat'"),
    "tsq": ("fat & cat", "'fat' & 'cat'"),
    "bt": (asyncpg.BitString.from_int(5, 3), asyncpg.BitString.from_int(5, 3)),
    "vb": (asyncpg.BitString.from_int(1, 1), asyncpg.BitString.from_int(1, 1)),
    "r4": (R(1, 10), R(1, 10)),
    "r8": (R(None, 2**40, upper_inc=True), R(None, 2**40 + 1)),
    "rn": (R(decimal.Decimal("1.5"), decimal.Decimal("2.5")), R(decimal.Decimal("1.5"), decimal.Decimal("2.5"))),
    "rd": (R(datetime.date(2020, 1, 1), datetime.date(2020, 2, 1)), R(datetime.date(2020, 1, 1), datetime.date(2020, 2, 1))),
    "rts": (R(datetime.datetime(2020, 1, 1), None), R(datetime.datetime(2020, 1, 1), None)),
    "rtstz": (R(empty=True), R(empty=True)),
    "m4": ([R(1, 3), R(5, 7)], [R(1, 3), R(5, 7)]),
    "m8": ([], []),
    "mn": ([R(decimal.Decimal(1), decimal.Decimal(2))], [R(decimal.Decimal(1), decimal.Decimal(2))]),
    "md": ([R(datetime.date(2020, 1, 1), datetime.date(2020, 1, 5))], [R(datetime.date(2020, 1, 1), datetime.date(2020, 1, 5))]),
    "mts": ([R(datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 2))], [R(datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 2))]),
    "mtstz": ([R(datetime.datetime(2020, 1, 1, tzinfo=UTC), None)], [R(datetime.datetime(2020, 1, 1, tzinfo=UTC), None)]),
    "pt": (asyncpg.Point(1, 2), asyncpg.Point(1, 2)),
    "ln": (asyncpg.Line(1, 2, 3), asyncpg.Line(1, 2, 3)),
    "ls": (asyncpg.LineSegment((0, 0), (1, 1)), asyncpg.LineSegment((0, 0), (1, 1))),
    "bx": (asyncpg.Box((2, 2), (0, 0)), asyncpg.Box((2, 2), (0, 0))),
    "pth": (asyncpg.Path((0, 0), (1, 1), (2, 0), is_closed=True), asyncpg.Path((0, 0), (1, 1), (2, 0), is_closed=True)),
    "pg": (asyncpg.Polygon((0, 0), (1, 1), (2, 0)), asyncpg.Polygon((0, 0), (1, 1), (2, 0))),
    "cr": (asyncpg.Circle(asyncpg.Point(0, 0), 5), asyncpg.Circle(asyncpg.Point(0, 0), 5)),
    "o": (4294967295, 4294967295),
    "hs": ('a=>1, "b c"=>NULL', '"a"=>"1", "b c"=>NULL'),
    "lt": ("top.middle.leaf", "top.middle.leaf"),
    "en": (models.Mood.HAPPY, models.Mood.HAPPY),
    "dom": (42, 42),
    "comp": ((1, "x"), (1, "x")),
}

ARRAY_SKIP = {"dom"}
# asyncpg can't bind arrays of multiranges/paths/polygons (nested sequences
# read as dimensions); tested read-only.
ARRAY_WRITE_SKIP = ARRAY_SKIP | {"m4", "m8", "mn", "md", "mts", "mtstz", "pth", "pg"}


def _norm(v: Any) -> Any:
    if isinstance(v, asyncpg.Record):
        return tuple(v)
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, (asyncpg.Path, asyncpg.Polygon)):
        return (type(v).__name__, tuple(tuple(p) for p in v), getattr(v, "is_closed", None))
    return v


def params(**override: Any) -> query.InsertAllTypesParams:
    kw: dict[str, Any] = {}
    for name, (sent, _) in SAMPLES.items():
        kw[name] = sent
        kw[name + "_null"] = None
        if name not in ARRAY_SKIP:
            kw[name + "_arr"] = None
    kw.update(override)
    return query.InsertAllTypesParams(**kw)


def expected(row: models.AllType, **override: Any) -> None:
    for name, (_, exp) in SAMPLES.items():
        got = getattr(row, name)
        assert _norm(got) == _norm(exp), f"{name}: {got!r} != {exp!r}"
        assert getattr(row, name + "_null") is None
        if name not in ARRAY_SKIP:
            assert getattr(row, name + "_arr") is None
    for k, v in override.items():
        assert _norm(getattr(row, k)) == _norm(v), f"{k}: {getattr(row, k)!r} != {v!r}"


async def test_roundtrip_not_null(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    row = await q.insert_all_types(params())
    assert row is not None
    conforms(row, models.AllType)
    expected(row)
    again = await q.get_all_types(row.id)
    assert again is not None
    conforms(again, models.AllType)
    expected(again)
    assert await q.get_all_types(row.id + 1) is None
    rows = await q.list_all_types()
    check_return(q.list_all_types, rows)


async def test_roundtrip_nullable_and_arrays(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    over: dict[str, Any] = {}
    exp: dict[str, Any] = {}
    for name, (sent, back) in SAMPLES.items():
        over[name + "_null"] = sent
        exp[name + "_null"] = back
        if name not in ARRAY_WRITE_SKIP:
            over[name + "_arr"] = [sent, None, sent]
            exp[name + "_arr"] = [back, None, back]
    row = await q.insert_all_types(params(**over))
    assert row is not None
    conforms(row, models.AllType)
    for k, v in exp.items():
        assert _norm(getattr(row, k)) == _norm(v), f"{k}: {getattr(row, k)!r} != {v!r}"
    assert type(row.en_null) is models.Mood
    assert row.en_arr is not None and type(row.en_arr[0]) is models.Mood and row.en_arr[1] is None


async def test_empty_arrays(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    over: dict[str, Any] = {name + "_arr": [] for name in SAMPLES if name not in ARRAY_WRITE_SKIP}
    row = await q.insert_all_types(params(**over))
    assert row is not None
    conforms(row, models.AllType)
    for k in over:
        assert getattr(row, k) == [], k


async def test_copyfrom_all_types(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    p = params()
    kw = {f: getattr(p, f) for f in p.__struct_fields__}
    n = await q.copy_all_types([query.CopyAllTypesParams(**kw), query.CopyAllTypesParams(**kw)])
    assert n == 2
    rows = await q.list_all_types()
    assert len(rows) == 2
    for r in rows:
        conforms(r, models.AllType)
        expected(r)


async def test_echo_queries(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    row = await q.insert_all_types(params(**{n + "_null": s for n, (s, _) in SAMPLES.items()}))
    assert row is not None
    for name, (sent, back) in SAMPLES.items():
        method = getattr(q, "echo_" + name.replace("_", ""))
        hints = typing.get_type_hints(method)
        (arg_name, arg_type), *_ = [(k, v) for k, v in hints.items() if k != "return"]
        arg = row.id if arg_name == "id" else getattr(row, name)
        res = await method(arg)
        assert res is not None, name
        check_return(method, res)
        assert _norm(getattr(res, name)) == _norm(back), name
        assert _norm(getattr(res, name + "_null")) == _norm(back), name


async def test_multi_dim(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    row = await q.insert_multi_dim(
        query.InsertMultiDimParams(
            grid=[[1, 2], [3, 4]],
            cube=[[["a"], ["b"]], [["c"], ["d"]]],
            moods=[[models.Mood.SAD, models.Mood.OK], [models.Mood.HAPPY, models.Mood.SAD]],
        )
    )
    assert row is not None
    conforms(row, models.MultiDim)
    assert row.grid == [[1, 2], [3, 4]]
    assert row.cube == [[["a"], ["b"]], [["c"], ["d"]]]
    assert row.moods == [[models.Mood.SAD, models.Mood.OK], [models.Mood.HAPPY, models.Mood.SAD]]
    assert row.moods is not None and type(row.moods[1][0]) is models.Mood
    row2 = await q.insert_multi_dim(query.InsertMultiDimParams(grid=[], cube=None, moods=None))
    assert row2 is not None and row2.grid == [] and row2.cube is None and row2.moods is None


async def test_scalar_casts_and_nulls(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    u = uuid.uuid4()
    r = await q.scalar_casts(query.ScalarCastsParams(7, ["a", "b"], models.Mood.OK, [models.Mood.SAD], u))
    assert r is not None
    check_return(q.scalar_casts, r)
    assert (r.i, r.arr, r.mood, r.moods, r.u) == (7, ["a", "b"], models.Mood.OK, [models.Mood.SAD], u)
    n = await q.null_literals()
    assert n is not None
    check_return(q.null_literals, n)
    assert (n.ni, n.nm, n.nma, n.nta) == (None, None, None, None)
    m = await q.mood_array_null_elems()
    check_return(q.mood_array_null_elems, m)
    assert m == [models.Mood.OK, None]


async def test_enum_str_param_accepted(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    r = await q.scalar_casts(query.ScalarCastsParams(1, [], "happy", ["ok"], uuid.uuid4()))  # type: ignore
    assert r is not None and r.mood is models.Mood.HAPPY and r.moods == [models.Mood.OK]


async def test_bad_enum_value_rejected(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    with pytest.raises(asyncpg.InvalidTextRepresentationError):
        await q.scalar_casts(query.ScalarCastsParams(1, [], "nope", [], uuid.uuid4()))  # type: ignore


def test_msgspec_type_info_supported_fields() -> None:
    msgspec.inspect.type_info(models.MultiDim)
    # msgspec can't decode the ipaddress unions
    with pytest.raises(TypeError, match="ipaddress"):
        msgspec.inspect.type_info(models.AllType)


def test_annotations_resolve() -> None:
    for cls in (models.AllType, models.MultiDim, query.InsertAllTypesParams, query.ScalarCastsRow):
        typing.get_type_hints(cls)


async def test_multirange_arrays_read(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    r = await q.multirange_array()
    check_return(q.multirange_array, r)
    assert r == [[R(1, 3)], [], [R(5, 6), R(8, 9)]]


async def test_geometry_arrays_read(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    r = await q.geometry_arrays()
    assert r is not None
    check_return(q.geometry_arrays, r)
    assert r.paths is not None and len(r.paths) == 2 and typing.cast(list[Any], r.paths)[1] is None
    assert r.polys is not None and len(r.polys) == 1


async def test_vector(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    e = await q.insert_embedding(query.InsertEmbeddingParams(v="[1,2,3]", v_null=None, v_arr=["[0,0,1]", None]))  # type: ignore
    assert e is not None
    conforms(e, models.Embedding)
    assert (e.v, e.v_null, e.v_arr) == ("[1,2,3]", None, ["[0,0,1]", None])
    near = await q.nearest_embedding("[1,2,4]")
    assert near is not None and near.id == e.id
    # no binary COPY encoder: executemany fallback
    assert await q.copy_embeddings([query.CopyEmbeddingsParams(v="[3,3,3]", v_null="[1,1,1]")] * 3) == 3
    rows = await q.list_embeddings()
    assert [r.v for r in rows] == ["[1,2,3]", "[3,3,3]", "[3,3,3]", "[3,3,3]"]
