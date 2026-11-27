-- name: InsertUser :one
INSERT INTO users (id, contact, backup, meta, extra, label, note, tags, created_at, created_by, amount)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) RETURNING *;

-- name: ByContact :many
SELECT id, contact FROM users WHERE contact = $1;

-- name: ByLabel :one
SELECT label, note FROM users WHERE label = $1;

-- name: InsertItem :one
INSERT INTO shop.items (id, price, created_at) VALUES ($1, $2, $3) RETURNING *;

-- name: MetaOnly :one
SELECT meta AS m FROM users WHERE id = $1;
