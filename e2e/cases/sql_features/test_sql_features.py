import datetime
import decimal
import inspect

import asyncpg

from cases.sql_features.gen import db, models, orders, products, querier
from conform import check_return

D = decimal.Decimal


async def setup(q: db.Queries) -> tuple[models.InvProduct, models.InvProduct]:
    a = await q.upsert_product(products.UpsertProductParams(sku="apple", unit=models.InvUnit.KG, price=D("2.50"), stock=10))
    b = await q.upsert_product(products.UpsertProductParams(sku="bolt", unit=models.InvUnit.PIECE, price=D("0.10"), stock=100))
    assert a is not None and b is not None
    return a, b


async def test_products(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    a, b = await setup(q)
    assert a.unit is models.InvUnit.KG
    again = await q.upsert_product(products.UpsertProductParams(sku="apple", unit=models.InvUnit.KG, price=D("3.00"), stock=5))
    assert again == models.InvProduct(id=a.id, sku="apple", unit=models.InvUnit.KG, price=D("3.00"), stock=15)
    assert await q.restock(products.RestockParams(product_id=a.id, amount=5)) == 20
    assert await q.restock(products.RestockParams(product_id=999, amount=5)) is None
    cheap = await q.cheap_products(D("1"))
    check_return(q.cheap_products, cheap)
    assert [p.sku for p in cheap] == ["bolt"]
    assert [r.sku for r in await q.products_page(products.ProductsPageParams(limit=1, offset=1))] == ["bolt"]
    assert await q.units_in_use() == [models.InvUnit.KG, models.InvUnit.PIECE]
    stats = await q.price_stats()
    check_return(q.price_stats, stats)
    assert stats == products.PriceStatsRow(min_price=D("0.10"), max_price=D("3.00"), avg_price=D("1.55"), n=2, total_stock=120)
    assert await q.delete_product_returning("bolt") == products.DeleteProductReturningRow(id=b.id, sku="bolt")
    assert await q.delete_product_returning("bolt") is None
    doc = inspect.getdoc(products.ProductsQueries.upsert_product)
    assert doc == "Insert or update a product by SKU.\nReturns the stored row."


async def test_orders(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    a, b = await setup(q)
    o1 = await q.place_order(orders.PlaceOrderParams(product_id=a.id, qty=3, note="first"))
    assert o1 is not None and o1.note == "first" and o1.placed_at.tzinfo is not None
    await q.place_order_exec(orders.PlaceOrderExecParams(product_id=b.id, qty=10))
    await q.place_order(orders.PlaceOrderParams(product_id=a.id, qty=1, note=None))
    totals = await q.order_totals()
    check_return(q.order_totals, totals)
    assert [(t.sku, t.total) for t in totals] == [("apple", D("7.50")), ("bolt", D("1.00")), ("apple", D("2.50"))]
    await q.refresh_sku_counts()
    assert await q.sku_counts() == [models.SkuCount(sku="apple", n=2), models.SkuCount(sku="bolt", n=1)]
    wp = await q.orders_with_product()
    check_return(q.orders_with_product, wp)
    assert [(r.order.qty, r.inv_product.sku) for r in wp] == [(3, "apple"), (10, "bolt"), (1, "apple")]
    emb = await q.order_total_embed()
    assert [r.order_total.sku for r in emb] == ["apple", "bolt", "apple"]
    assert all(isinstance(r.fetched_at, datetime.datetime) for r in emb)
    ranked = await q.ranked_orders()
    check_return(q.ranked_orders, ranked)
    assert [(r.rnk, r.running) for r in ranked] == [(2, 3), (1, 13), (3, 14)]
    latest = await q.latest_order_per_product()
    assert [(r.sku, r.qty) for r in latest] == [("apple", 1), ("bolt", 10)]
    moved = await q.moved_orders(5)
    assert [(m.qty) for m in moved] == [4, 2]
    assert await q.unioned() == ["apple", "bolt", "first"]
    cases = await q.case_expr()
    assert [(c.size, c.note_or_empty, c.no_note) for c in cases] == [("small", "first", False), ("big", "", True), ("small", "", True)]
    assert await q.series(3) == [1, 2, 3]
    assert await q.series(0) == []
    assert await q.order_exists(o1.id) is True
    assert await q.order_exists(999) is False
    assert await q.order_note_by_id(o1.id) == "first"
    assert await q.order_note_by_id(999) is None
    since = o1.placed_at - datetime.timedelta(minutes=1)
    assert len(await q.orders_since(orders.OrdersSinceParams(since=since, min_qty=None))) == 3
    assert len(await q.orders_since(orders.OrdersSinceParams(since=since, min_qty=4))) == 2
    assert await q.json_agg() == '[{"id" : 1, "qty" : 4}, {"id" : 2, "qty" : 10}, {"id" : 3, "qty" : 2}]'
    assert await q.array_agg() == [1, 2, 3]
    assert await q.delete_orders(a.id) == 2
    assert await q.delete_orders(a.id) == 0
    await q.create_temp()
    await q.create_temp()
    qi: querier.Querier = q
    assert await qi.order_exists(1) is False


async def test_empty_aggregates(conn: asyncpg.Connection) -> None:
    q = db.Queries(conn)
    assert await q.array_agg() is None
    assert await q.json_agg() == "[]"
    stats = await q.price_stats()
    assert stats == products.PriceStatsRow(min_price=None, max_price=None, avg_price=None, n=0, total_stock=0)  # type: ignore
