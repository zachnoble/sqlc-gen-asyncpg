import datetime
import decimal
import inspect

import asyncpg

from cases.analyzer.gen import models, orders, products
from conform import check_return

D = decimal.Decimal


async def setup(conn: asyncpg.Connection) -> tuple[models.InvProduct, models.InvProduct]:
    a = await products.upsert_product(conn, products.UpsertProductParams(sku="apple", unit=models.InvUnit.KG, price=D("2.50"), stock=10))
    b = await products.upsert_product(conn, products.UpsertProductParams(sku="bolt", unit=models.InvUnit.PIECE, price=D("0.10"), stock=100))
    assert a is not None and b is not None
    return a, b


async def test_products(conn: asyncpg.Connection) -> None:
    a, b = await setup(conn)
    assert a.unit is models.InvUnit.KG
    again = await products.upsert_product(conn, products.UpsertProductParams(sku="apple", unit=models.InvUnit.KG, price=D("3.00"), stock=5))
    assert again == models.InvProduct(id=a.id, sku="apple", unit=models.InvUnit.KG, price=D("3.00"), stock=15)
    assert await products.restock(conn, products.RestockParams(product_id=a.id, amount=5)) == 20
    assert await products.restock(conn, products.RestockParams(product_id=999, amount=5)) is None
    cheap = await products.cheap_products(conn, D("1"))
    check_return(products.cheap_products, cheap)
    assert [p.sku for p in cheap] == ["bolt"]
    assert [r.sku for r in await products.products_page(conn, products.ProductsPageParams(limit=1, offset=1))] == ["bolt"]
    assert await products.units_in_use(conn) == [models.InvUnit.KG, models.InvUnit.PIECE]
    stats = await products.price_stats(conn)
    check_return(products.price_stats, stats)
    assert stats == products.PriceStatsRow(min_price=D("0.10"), max_price=D("3.00"), avg_price=D("1.55"), n=2, total_stock=120)
    assert await products.delete_product_returning(conn, "bolt") == products.DeleteProductReturningRow(id=b.id, sku="bolt")
    assert await products.delete_product_returning(conn, "bolt") is None
    doc = inspect.getdoc(products.upsert_product)
    assert doc == "Insert or update a product by SKU.\nReturns the stored row."


async def test_orders(conn: asyncpg.Connection) -> None:
    a, b = await setup(conn)
    o1 = await orders.place_order(conn, orders.PlaceOrderParams(product_id=a.id, qty=3, note="first"))
    assert o1 is not None and o1.note == "first" and o1.placed_at.tzinfo is not None
    await orders.place_order_exec(conn, orders.PlaceOrderExecParams(product_id=b.id, qty=10))
    await orders.place_order(conn, orders.PlaceOrderParams(product_id=a.id, qty=1, note=None))
    totals = await orders.order_totals(conn)
    check_return(orders.order_totals, totals)
    assert [(t.sku, t.total) for t in totals] == [("apple", D("7.50")), ("bolt", D("1.00")), ("apple", D("2.50"))]
    await orders.refresh_sku_counts(conn)
    assert await orders.sku_counts(conn) == [models.SkuCount(sku="apple", n=2), models.SkuCount(sku="bolt", n=1)]
    wp = await orders.orders_with_product(conn)
    check_return(orders.orders_with_product, wp)
    assert [(r.order.qty, r.inv_product.sku) for r in wp] == [(3, "apple"), (10, "bolt"), (1, "apple")]
    emb = await orders.order_total_embed(conn)
    assert [r.order_total.sku for r in emb] == ["apple", "bolt", "apple"]
    assert all(isinstance(r.fetched_at, datetime.datetime) for r in emb)
    ranked = await orders.ranked_orders(conn)
    check_return(orders.ranked_orders, ranked)
    assert [(r.rnk, r.running) for r in ranked] == [(2, 3), (1, 13), (3, 14)]
    latest = await orders.latest_order_per_product(conn)
    assert [(r.sku, r.qty) for r in latest] == [("apple", 1), ("bolt", 10)]
    moved = await orders.moved_orders(conn, 5)
    assert [(m.qty) for m in moved] == [4, 2]
    assert await orders.unioned(conn) == ["apple", "bolt", "first"]
    cases = await orders.case_expr(conn)
    assert [(c.size, c.note_or_empty, c.no_note) for c in cases] == [("small", "first", False), ("big", "", True), ("small", "", True)]
    assert await orders.series(conn, 3) == [1, 2, 3]
    assert await orders.series(conn, 0) == []
    assert await orders.order_exists(conn, o1.id) is True
    assert await orders.order_exists(conn, 999) is False
    assert await orders.order_note_by_id(conn, o1.id) == "first"
    assert await orders.order_note_by_id(conn, 999) is None
    since = o1.placed_at - datetime.timedelta(minutes=1)
    assert len(await orders.orders_since(conn, orders.OrdersSinceParams(since=since, min_qty=None))) == 3
    assert len(await orders.orders_since(conn, orders.OrdersSinceParams(since=since, min_qty=4))) == 2
    assert await orders.json_agg(conn) == '[{"id" : 1, "qty" : 4}, {"id" : 2, "qty" : 10}, {"id" : 3, "qty" : 2}]'
    assert await orders.array_agg(conn) == [1, 2, 3]
    assert await orders.delete_orders(conn, a.id) == 2
    assert await orders.delete_orders(conn, a.id) == 0
    await orders.create_temp(conn)
    await orders.create_temp(conn)


async def test_empty_aggregates(conn: asyncpg.Connection) -> None:
    assert await orders.array_agg(conn) is None
    assert await orders.json_agg(conn) == "[]"
    stats = await products.price_stats(conn)
    assert stats == products.PriceStatsRow(min_price=None, max_price=None, avg_price=None, n=0, total_stock=0)  # type: ignore


def test_analyzer_inference() -> None:
    import typing

    assert typing.get_type_hints(orders.CaseExprRow)["no_note"] == bool | None
