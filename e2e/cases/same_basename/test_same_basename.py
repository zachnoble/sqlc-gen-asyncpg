import asyncpg

from cases.same_basename.gen import q


async def test_merged_module(conn: asyncpg.Connection) -> None:
    assert await q.get_t(conn, 1) is None
    assert await q.other(conn) == 1
