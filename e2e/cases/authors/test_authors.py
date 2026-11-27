import decimal
import inspect
import typing

import asyncpg
import msgspec
import pytest

from cases.authors.gen import batch, copyfrom, db, models, query


async def test_crud(conn: asyncpg.Connection) -> None:
    assert await query.get_author(conn, 1) is None
    a = await query.create_author(conn, query.CreateAuthorParams(name="Brian", bio=None))
    assert a == models.Author(id=1, name="Brian", bio=None)
    assert type(a) is models.Author
    b = await query.create_author(conn, query.CreateAuthorParams(name="Alice", bio="bio"))
    assert b is not None and b.id == 2
    assert await query.get_author(conn, 1) == a
    assert await query.list_authors(conn) == [b, a]  # ordered by name
    assert await query.count_authors(conn) == 2
    assert await query.author_bio(conn, 2) == "bio"
    assert await query.author_bio(conn, 1) is None
    assert await query.author_bio(conn, 999) is None
    await query.delete_author(conn, 1)
    assert await query.get_author(conn, 1) is None
    assert await query.list_authors(conn) == [b]


async def test_execrows_and_execresult(conn: asyncpg.Connection) -> None:
    for n in ["ann", "anna", "bob"]:
        await query.create_author(conn, query.CreateAuthorParams(name=n, bio=None))
    assert await query.update_bios(conn, query.UpdateBiosParams(bio="x", pattern="ann%")) == 2
    assert await query.update_bios(conn, query.UpdateBiosParams(bio="x", pattern="zzz%")) == 0
    assert await query.touch_authors(conn) == "UPDATE 3"


async def test_enums(conn: asyncpg.Connection) -> None:
    a = await query.create_author(conn, query.CreateAuthorParams(name="a", bio=None))
    assert a is not None
    for kind in models.BookType:
        book = await query.create_book(conn, 
            query.CreateBookParams(
                author_id=a.id, title=str(kind), kind=kind, tags=["x", "y"], price=decimal.Decimal("1.50")
            )
        )
        assert book is not None
        assert book.kind is kind
        assert type(book.kind) is models.BookType
        assert book.price == decimal.Decimal("1.50")
        assert book.tags == ["x", "y"]
    rows = await query.books_by_kind(conn, models.BookType.SCI_FI)
    assert [(r.title, r.kind) for r in rows] == [("sci-fi", models.BookType.SCI_FI)]
    assert type(rows[0].kind) is models.BookType
    kinds = await query.book_kinds(conn)
    assert kinds == sorted(models.BookType, key=list(models.BookType).index)
    assert all(type(k) is models.BookType for k in kinds)
    assert models.BookType.A_B.value == "a b"


async def test_embed(conn: asyncpg.Connection) -> None:
    a = await query.create_author(conn, query.CreateAuthorParams(name="a", bio="b"))
    assert a is not None
    bk = await query.create_book(conn, 
        query.CreateBookParams(author_id=a.id, title="t", kind=models.BookType.FICTION, tags=[], price=None)
    )
    rows = await query.books_with_author(conn)
    assert rows == [query.BooksWithAuthorRow(book=bk, author=a)]  # type: ignore
    assert type(rows[0].book.kind) is models.BookType


async def test_arrays_slices_nargs(conn: asyncpg.Connection) -> None:
    for n in ["a", "b", "c"]:
        await query.create_author(conn, query.CreateAuthorParams(name=n, bio=n * 2))
    assert [r.id for r in await query.authors_by_ids(conn, [3, 1, 99])] == [1, 3]
    assert await query.authors_by_ids(conn, []) == []
    assert await query.authors_by_slice(conn, [2, 3]) == [2, 3]
    assert await query.authors_by_slice(conn, []) == []
    assert await query.authors_not_in_slice(conn, [2]) == [1, 3]
    assert await query.authors_not_in_slice(conn, []) == [1, 2, 3]
    assert await query.search_authors(conn, query.SearchAuthorsParams(name=None, bio=None)) == [1, 2, 3]
    assert await query.search_authors(conn, query.SearchAuthorsParams(name="b", bio=None)) == [2]
    assert await query.search_authors(conn, query.SearchAuthorsParams(name=None, bio="cc")) == [3]
    assert await query.search_authors(conn, query.SearchAuthorsParams(name="b", bio="cc")) == []


async def test_copyfrom(conn: asyncpg.Connection) -> None:
    n = await copyfrom.copy_authors(conn, [query.CopyAuthorsParams(name=f"n{i}", bio=None if i % 2 else "x") for i in range(100)])
    assert n == 100
    assert await copyfrom.copy_authors(conn, []) == 0
    authors = await query.list_authors(conn)
    assert len(authors) == 100
    assert sum(a.bio is None for a in authors) == 50
    assert await copyfrom.copy_book_titles(conn, 
        [query.CopyBookTitlesParams(author_id=1, title="t", kind=k) for k in models.BookType]
    ) == len(models.BookType)
    assert [r.kind for r in await query.books_by_kind(conn, models.BookType.A_B)] == [models.BookType.A_B]


async def test_batch(conn: asyncpg.Connection) -> None:
    await batch.batch_create_authors(conn, ["x", "y", "z"])
    await batch.batch_create_authors(conn, [])
    got = await batch.batch_get_author(conn, [3, 42, 1])
    assert got == [models.Author(id=3, name="z", bio=None), None, models.Author(id=1, name="x", bio=None)]
    await query.create_book(conn, query.CreateBookParams(author_id=1, title="b1", kind=models.BookType.FICTION, tags=[], price=None))
    await query.create_book(conn, query.CreateBookParams(author_id=1, title="b2", kind=models.BookType.FICTION, tags=[], price=None))
    many = await batch.batch_books_by_author(conn, [1, 2])
    assert [[r.title for r in rs] for rs in many] == [["b1", "b2"], []]
    assert await batch.batch_get_author(conn, []) == []


async def test_batch_is_atomic(conn: asyncpg.Connection) -> None:
    await batch.batch_create_authors(conn, ["x"])
    # executemany is atomic
    with pytest.raises(asyncpg.NotNullViolationError):
        await batch.batch_create_authors(conn, ["a", None, "b"])  # type: ignore
    assert [a.name for a in await query.list_authors(conn)] == ["x"]


async def test_pool_and_transaction(pool: asyncpg.Pool) -> None:
    a = await query.create_author(pool, query.CreateAuthorParams(name="p", bio=None))
    assert a is not None
    assert await batch.batch_get_author(pool, [a.id]) == [a]
    assert await batch.batch_books_by_author(pool, [a.id]) == [[]]
    await batch.batch_create_authors(pool, ["q"])
    assert await copyfrom.copy_authors(pool, [query.CopyAuthorsParams(name="c", bio=None)]) == 1
    async with pool.acquire() as c:
        tx = c.transaction()
        await tx.start()
        await query.create_author(c, query.CreateAuthorParams(name="rolled back", bio=None))
        assert len(await query.list_authors(c)) == 4
        assert await batch.batch_get_author(c, [a.id]) == [a]  # reuses the open transaction
        await tx.rollback()
    assert len(await query.list_authors(pool)) == 3


async def test_msgspec_roundtrip(conn: asyncpg.Connection) -> None:
    a = await query.create_author(conn, query.CreateAuthorParams(name="j", bio=None))
    assert a is not None
    raw = msgspec.json.encode(a)
    assert msgspec.json.decode(raw) == {"id": a.id, "name": "j", "bio": None}
    assert msgspec.json.decode(raw, type=models.Author) == a
    params = msgspec.convert({"name": "k", "bio": "z"}, query.CreateAuthorParams)
    assert (await query.create_author(conn, params)) == models.Author(id=a.id + 1, name="k", bio="z")
    book = msgspec.convert(
        {"book_id": 1, "author_id": 1, "title": "t", "kind": "sci-fi", "tags": [], "price": "1.2"}, models.Book
    )
    assert book.kind is models.BookType.SCI_FI
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert({"book_id": 1, "author_id": 1, "title": "t", "kind": "nope", "tags": [], "price": None}, models.Book)


def test_docstrings_and_comments() -> None:
    assert models.Author.__doc__ == "Authors write books."
    assert inspect.getdoc(query.list_authors) == "Lists all authors ordered by name."


def test_function_signatures() -> None:
    assert list(inspect.signature(query.get_author).parameters) == ["conn", "id"]
    hints = typing.get_type_hints(query.get_author)
    assert hints["return"] == models.Author | None
    assert hints["conn"] is db.DBTX
    assert not hasattr(db, "Queries")


async def test_left_join_embed_documented_behaviour(conn: asyncpg.Connection) -> None:
    # sqlc marks embeds non-nullable even under LEFT JOIN; fields come back None.
    a = await query.create_author(conn, query.CreateAuthorParams(name="lonely", bio=None))
    assert a is not None
    (row,) = await query.authors_left_join_books(conn)
    assert row.author == a
    assert row.book == models.Book(book_id=None, author_id=None, title=None, kind=None, tags=None, price=None)  # type: ignore
