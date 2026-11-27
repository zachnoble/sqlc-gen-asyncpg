-- name: GetUser :one
-- Fetch one user.
SELECT * FROM users WHERE user_id = $1;

-- name: ListUsers :many
SELECT * FROM users ORDER BY user_id;

-- name: CreateUser :one
INSERT INTO users (user_name, email_addr, status) VALUES ($1, $2, $3) RETURNING *;

-- name: CreateUserTwo :one
INSERT INTO users (user_name, email_addr) VALUES ($1, $2) RETURNING user_id;

-- name: SetStatus :execrows
UPDATE users SET status = $2 WHERE user_id = $1;

-- name: DeleteAll :exec
DELETE FROM users;

-- name: Touch :execresult
UPDATE users SET user_name = user_name WHERE user_id = ANY(@ids::bigint[]);

-- name: FindUsers :many
SELECT user_id, user_name FROM users
WHERE user_name LIKE @pattern AND status = @status AND user_id > @min_id AND user_id < @max_id
ORDER BY user_id
LIMIT @lim;

-- name: CountUsers :one
SELECT count(*) AS total FROM users;

-- name: Fail :exec
INSERT INTO users (user_id, user_name) VALUES ($1, 'dup');

-- name: GetPerson :one
SELECT * FROM people WHERE id = $1;

-- name: CopyUsers :copyfrom
INSERT INTO users (user_name, email_addr, status) VALUES ($1, $2, $3);

-- name: BatchStatus :batchexec
UPDATE users SET status = $2 WHERE user_id = $1;

-- name: BatchGet :batchone
SELECT user_id, user_name FROM users WHERE user_id = $1;

-- name: BatchNames :batchmany
SELECT user_name FROM users WHERE status = $1 ORDER BY user_id;
