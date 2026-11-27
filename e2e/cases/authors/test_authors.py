import decimal
import inspect
import typing

import asyncpg
import msgspec
import pytest

from cases.authors.gen import batch, copyfrom, db, models, querier, query


async def test_crud(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    assert await q.get_author(1) is None
    a = await q.create_author(query.CreateAuthorParams(name="Brian", bio=None))
    assert a == models.Author(id=1, name="Brian", bio=None)
    assert type(a) is models.Author
    b = await q.create_author(query.CreateAuthorParams(name="Alice", bio="bio"))
    assert b is not None and b.id == 2
    assert await q.get_author(1) == a
    assert await q.list_authors() == [b, a]  # ordered by name
    assert await q.count_authors() == 2
    assert await q.author_bio(2) == "bio"
    assert await q.author_bio(1) is None
    assert await q.author_bio(999) is None
    await q.delete_author(1)
    assert await q.get_author(1) is None
    assert await q.list_authors() == [b]


async def test_execrows_and_execresult(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    for n in ["ann", "anna", "bob"]:
        await q.create_author(query.CreateAuthorParams(name=n, bio=None))
    assert await q.update_bios(query.UpdateBiosParams(bio="x", pattern="ann%")) == 2
    assert await q.update_bios(query.UpdateBiosParams(bio="x", pattern="zzz%")) == 0
    assert await q.touch_authors() == "UPDATE 3"


async def test_enums(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    a = await q.create_author(query.CreateAuthorParams(name="a", bio=None))
    assert a is not None
    for kind in models.BookType:
        book = await q.create_book(
            query.CreateBookParams(
                author_id=a.id, title=str(kind), kind=kind, tags=["x", "y"], price=decimal.Decimal("1.50")
            )
        )
        assert book is not None
        assert book.kind is kind
        assert type(book.kind) is models.BookType
        assert book.price == decimal.Decimal("1.50")
        assert book.tags == ["x", "y"]
    rows = await q.books_by_kind(models.BookType.SCI_FI)
    assert [(r.title, r.kind) for r in rows] == [("sci-fi", models.BookType.SCI_FI)]
    assert type(rows[0].kind) is models.BookType
    kinds = await q.book_kinds()
    assert kinds == sorted(models.BookType, key=list(models.BookType).index)
    assert all(type(k) is models.BookType for k in kinds)
    assert models.BookType.A_B.value == "a b"


async def test_embed(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    a = await q.create_author(query.CreateAuthorParams(name="a", bio="b"))
    assert a is not None
    bk = await q.create_book(
        query.CreateBookParams(author_id=a.id, title="t", kind=models.BookType.FICTION, tags=[], price=None)
    )
    rows = await q.books_with_author()
    assert rows == [query.BooksWithAuthorRow(book=bk, author=a)]  # type: ignore
    assert type(rows[0].book.kind) is models.BookType


async def test_arrays_slices_nargs(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    for n in ["a", "b", "c"]:
        await q.create_author(query.CreateAuthorParams(name=n, bio=n * 2))
    assert [r.id for r in await q.authors_by_ids([3, 1, 99])] == [1, 3]
    assert await q.authors_by_ids([]) == []
    assert await q.authors_by_slice([2, 3]) == [2, 3]
    assert await q.authors_by_slice([]) == []
    assert await q.authors_not_in_slice([2]) == [1, 3]
    assert await q.authors_not_in_slice([]) == [1, 2, 3]
    assert await q.search_authors(query.SearchAuthorsParams(name=None, bio=None)) == [1, 2, 3]
    assert await q.search_authors(query.SearchAuthorsParams(name="b", bio=None)) == [2]
    assert await q.search_authors(query.SearchAuthorsParams(name=None, bio="cc")) == [3]
    assert await q.search_authors(query.SearchAuthorsParams(name="b", bio="cc")) == []


async def test_copyfrom(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    n = await q.copy_authors([query.CopyAuthorsParams(name=f"n{i}", bio=None if i % 2 else "x") for i in range(100)])
    assert n == 100
    assert await q.copy_authors([]) == 0
    authors = await q.list_authors()
    assert len(authors) == 100
    assert sum(a.bio is None for a in authors) == 50
    assert await q.copy_book_titles(
        [query.CopyBookTitlesParams(author_id=1, title="t", kind=k) for k in models.BookType]
    ) == len(models.BookType)
    assert [r.kind for r in await q.books_by_kind(models.BookType.A_B)] == [models.BookType.A_B]


async def test_batch(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    await q.batch_create_authors(["x", "y", "z"])
    await q.batch_create_authors([])
    got = await q.batch_get_author([3, 42, 1])
    assert got == [models.Author(id=3, name="z", bio=None), None, models.Author(id=1, name="x", bio=None)]
    await q.create_book(query.CreateBookParams(author_id=1, title="b1", kind=models.BookType.FICTION, tags=[], price=None))
    await q.create_book(query.CreateBookParams(author_id=1, title="b2", kind=models.BookType.FICTION, tags=[], price=None))
    many = await q.batch_books_by_author([1, 2])
    assert [[r.title for r in rs] for rs in many] == [["b1", "b2"], []]
    assert await q.batch_get_author([]) == []


async def test_batch_is_atomic(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    await q.batch_create_authors(["x"])
    # executemany is atomic
    with pytest.raises(asyncpg.NotNullViolationError):
        await q.batch_create_authors(["a", None, "b"])  # type: ignore
    assert [a.name for a in await q.list_authors()] == ["x"]


async def test_pool_and_with_tx(pool: asyncpg.Pool) -> None:
    q = db.Queries(pool)
    a = await q.create_author(query.CreateAuthorParams(name="p", bio=None))
    assert a is not None
    assert await q.batch_get_author([a.id]) == [a]
    assert await q.batch_books_by_author([a.id]) == [[]]
    await q.batch_create_authors(["q"])
    assert await q.copy_authors([query.CopyAuthorsParams(name="c", bio=None)]) == 1
    async with pool.acquire() as c:
        tx = c.transaction()
        await tx.start()
        qt = q.with_tx(c)
        await qt.create_author(query.CreateAuthorParams(name="rolled back", bio=None))
        assert len(await qt.list_authors()) == 4
        await tx.rollback()
    assert len(await q.list_authors()) == 3


async def test_msgspec_roundtrip(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    a = await q.create_author(query.CreateAuthorParams(name="j", bio=None))
    assert a is not None
    raw = msgspec.json.encode(a)
    assert msgspec.json.decode(raw) == {"id": a.id, "name": "j", "bio": None}
    assert msgspec.json.decode(raw, type=models.Author) == a
    params = msgspec.convert({"name": "k", "bio": "z"}, query.CreateAuthorParams)
    assert (await q.create_author(params)) == models.Author(id=a.id + 1, name="k", bio="z")
    book = msgspec.convert(
        {"book_id": 1, "author_id": 1, "title": "t", "kind": "sci-fi", "tags": [], "price": "1.2"}, models.Book
    )
    assert book.kind is models.BookType.SCI_FI
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert({"book_id": 1, "author_id": 1, "title": "t", "kind": "nope", "tags": [], "price": None}, models.Book)


def test_docstrings_and_comments() -> None:
    assert models.Author.__doc__ == "Authors write books."
    assert inspect.getdoc(query.QueryQueries.list_authors) == "Lists all authors ordered by name."


def test_querier_protocol() -> None:
    hints = typing.get_type_hints(querier.Querier.get_author, globalns=vars(querier) | {"models": models})
    assert hints["return"] == models.Author | None
    assert issubclass(db.Queries, batch.BatchQueries)
    assert issubclass(db.Queries, copyfrom.CopyFromQueries)


async def test_left_join_embed_documented_behaviour(conn: asyncpg.Connection) -> None:
    # sqlc marks embeds non-nullable even under LEFT JOIN; fields come back None.
    q = db.Queries(conn)
    a = await q.create_author(query.CreateAuthorParams(name="lonely", bio=None))
    assert a is not None
    (row,) = await q.authors_left_join_books()
    assert row.author == a
    assert row.book == models.Book(book_id=None, author_id=None, title=None, kind=None, tags=None, price=None)  # type: ignore
