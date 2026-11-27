CREATE SCHEMA inv;
CREATE TYPE inv.unit AS ENUM ('kg', 'piece');

CREATE TABLE inv.products (
  id    serial PRIMARY KEY,
  sku   text NOT NULL UNIQUE,
  unit  inv.unit NOT NULL,
  price numeric(10,2) NOT NULL,
  stock int NOT NULL DEFAULT 0
);

CREATE TABLE orders (
  id         bigserial PRIMARY KEY,
  product_id int NOT NULL REFERENCES inv.products(id),
  qty        int NOT NULL,
  placed_at  timestamptz NOT NULL DEFAULT now(),
  note       text
);

CREATE VIEW order_totals AS
SELECT o.id, p.sku, o.qty * p.price AS total
FROM orders o JOIN inv.products p ON p.id = o.product_id;

CREATE MATERIALIZED VIEW sku_counts AS
SELECT p.sku, count(o.id) AS n FROM inv.products p LEFT JOIN orders o ON o.product_id = p.id GROUP BY p.sku;

CREATE FUNCTION inv.restock(pid int, amount int) RETURNS int LANGUAGE sql AS $$
  UPDATE inv.products SET stock = stock + amount WHERE id = pid RETURNING stock;
$$;

CREATE FUNCTION cheap_products(max_price numeric) RETURNS SETOF inv.products LANGUAGE sql AS $$
  SELECT * FROM inv.products WHERE price <= max_price ORDER BY id;
$$;
