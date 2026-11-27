-- name: UpsertProduct :one
-- Insert or update a product by SKU.
-- Returns the stored row.
INSERT INTO inv.products (sku, unit, price, stock) VALUES ($1, $2, $3, $4)
ON CONFLICT (sku) DO UPDATE SET price = EXCLUDED.price, stock = inv.products.stock + EXCLUDED.stock
RETURNING *;

-- name: Restock :one
SELECT inv.restock(@product_id, @amount)::int AS stock;

-- name: CheapProducts :many
SELECT * FROM cheap_products(@max_price::numeric);

-- name: ProductsPage :many
SELECT id, sku FROM inv.products ORDER BY id LIMIT $1 OFFSET $2;

-- name: UnitsInUse :many
SELECT DISTINCT unit FROM inv.products ORDER BY unit;

-- name: DeleteProductReturning :one
DELETE FROM inv.products WHERE sku = $1 RETURNING id, sku;

-- name: PriceStats :one
SELECT min(price)::numeric AS min_price, max(price)::numeric AS max_price, avg(price)::numeric AS avg_price,
       count(*) AS n, coalesce(sum(stock), 0)::bigint AS total_stock
FROM inv.products;
