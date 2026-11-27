import datetime
import decimal
import typing

import asyncpg
import msgspec

from cases.overrides import custom_types
from cases.overrides.gen import models, query
from cases.overrides.gen_order import models as order_models
from conform import check_return, conforms

UTC = datetime.timezone.utc


async def json_codec(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=lambda v: msgspec.json.encode(v).decode(),
        decoder=msgspec.json.decode,
        schema="pg_catalog",
    )


def test_annotations() -> None:
    hints = typing.get_type_hints(models.User)
    assert hints["contact"] is custom_types.Email
    assert hints["backup"] == custom_types.Email | None
    assert hints["meta"] == dict[str, typing.Any]
    assert hints["extra"] == dict[str, typing.Any] | None
    assert hints["label"] is custom_types.Label
    assert hints["note"] == str | None  # only the NOT NULL text override exists
    assert hints["tags"] == list[custom_types.Label]  # db_type overrides apply to array elements
    assert hints["created_at"] is datetime.datetime
    assert hints["author"] is str  # global rename + column override (listed first)
    assert hints["amount"] is decimal.Decimal
    assert typing.get_type_hints(models.ShopItem)["price"] is float  # schema qualified column override
    assert typing.get_type_hints(order_models.User)["author"] is datetime.datetime  # first match wins
    assert typing.get_type_hints(query.by_contact)["contact"] is custom_types.Email
    assert typing.get_type_hints(query.by_label)["label"] is custom_types.Label


async def test_runtime_with_codec(conn: asyncpg.Connection) -> None:
    await json_codec(conn)
    now = datetime.datetime(2024, 5, 1, tzinfo=UTC)
    u = await query.insert_user(conn, 
        query.InsertUserParams(
            id=1, contact=custom_types.Email("a@b"), backup=None, meta={"k": [1, 2]}, extra=None,
            label=custom_types.Label("L"), note=None, tags=[custom_types.Label("t")], created_at=now,
            author="me", amount=decimal.Decimal("2.5"),
        )
    )
    assert u is not None
    conforms(u, models.User)
    assert u.meta == {"k": [1, 2]} and u.extra is None
    assert await query.meta_only(conn, 1) == {"k": [1, 2]}
    rows = await query.by_contact(conn, custom_types.Email("a@b"))
    check_return(query.by_contact, rows)
    assert [r.id for r in rows] == [1]
    lab = await query.by_label(conn, custom_types.Label("L"))
    assert lab is not None and lab.label == "L" and lab.note is None
    item = await query.insert_item(conn, query.InsertItemParams(id=1, price=1.25, created_at=now))
    assert item is not None and item.created_at == now
    data = msgspec.json.encode(u)
    assert msgspec.json.decode(data, type=models.User) == u
