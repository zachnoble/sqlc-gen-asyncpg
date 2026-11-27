-- name: GetT :one
SELECT * FROM t WHERE id = $1;
