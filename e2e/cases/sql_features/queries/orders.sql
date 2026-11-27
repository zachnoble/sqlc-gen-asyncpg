-- name: PlaceOrder :one
INSERT INTO orders (product_id, qty, note) VALUES ($1, $2, $3) RETURNING *;

-- name: PlaceOrderExec :exec
INSERT INTO orders (product_id, qty) VALUES ($1, $2) RETURNING id;

-- name: OrderTotals :many
SELECT * FROM order_totals ORDER BY id;

-- name: RefreshSkuCounts :exec
REFRESH MATERIALIZED VIEW sku_counts;

-- name: SkuCounts :many
SELECT * FROM sku_counts ORDER BY sku;

-- name: OrdersWithProduct :many
SELECT sqlc.embed(orders), sqlc.embed(products)
FROM orders JOIN inv.products AS products ON products.id = orders.product_id
ORDER BY orders.id;

-- name: OrderTotalEmbed :many
SELECT sqlc.embed(order_totals), now() AS fetched_at FROM order_totals ORDER BY id;

-- name: RankedOrders :many
SELECT id, qty, rank() OVER (ORDER BY qty DESC, id) AS rnk,
       sum(qty) OVER (ORDER BY id) AS running
FROM orders ORDER BY id;

-- name: LatestOrderPerProduct :many
SELECT p.sku, latest.id AS order_id, latest.qty
FROM inv.products p
CROSS JOIN LATERAL (SELECT id, qty FROM orders o WHERE o.product_id = p.id ORDER BY id DESC LIMIT 1) latest
ORDER BY p.sku;

-- name: MovedOrders :many
WITH moved AS (
  UPDATE orders SET qty = qty + 1 WHERE qty < @below RETURNING id, qty
)
SELECT id, qty FROM moved ORDER BY id;

-- name: Unioned :many
SELECT sku AS label FROM inv.products
UNION ALL
SELECT note FROM orders WHERE note IS NOT NULL
ORDER BY label;

-- name: CaseExpr :many
SELECT id, CASE WHEN qty > 5 THEN 'big' ELSE 'small' END AS size, coalesce(note, '') AS note_or_empty,
       note IS NULL AS no_note
FROM orders ORDER BY id;

-- name: Series :many
SELECT g::int AS n FROM generate_series(1, @upto::int) AS g;

-- name: OrderExists :one
SELECT EXISTS (SELECT 1 FROM orders WHERE id = $1) AS found;

-- name: OrderNoteByID :one
SELECT note FROM orders WHERE id = $1;

-- name: OrdersSince :many
SELECT id FROM orders WHERE placed_at >= sqlc.arg(since)::timestamptz AND (sqlc.narg(min_qty)::int IS NULL OR qty >= sqlc.narg(min_qty)) ORDER BY id;

-- name: JsonAgg :one
SELECT coalesce(json_agg(json_build_object('id', id, 'qty', qty) ORDER BY id), '[]')::text AS doc FROM orders;

-- name: ArrayAgg :one
SELECT array_agg(id ORDER BY id)::bigint[] AS ids FROM orders;

-- name: DeleteOrders :execrows
DELETE FROM orders WHERE product_id = $1;

-- name: CreateTemp :exec
CREATE TEMP TABLE IF NOT EXISTS scratch (x int);
