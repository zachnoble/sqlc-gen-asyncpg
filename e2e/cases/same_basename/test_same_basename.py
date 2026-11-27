import asyncpg

from cases.same_basename.gen import db


async def test_merged_module(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    assert await q.get_t(1) is None
    assert await q.other() == 1
