-- name: InsertClass :one
INSERT INTO "class" ("from", "def", "None", "True", "self", id, "type", "list", "datetime", "decimal", "uuid", "typing", "models",
  "msgspec", "asyncpg", "ipaddress", "collections", "enum", "conn", "arg", "args", "_row", "_rows", "_stmt", "_out", "_status", "_n",
  "_a", "_records", "first name", "first_name", "2fa", "café", "Name", "name", "__secret", "WeirdEnum", "OtherWeirdEnum")
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27,
  $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38)
RETURNING *;

-- name: GetClass :one
SELECT * FROM "class" WHERE id = $1;

-- name: ParamsNamedLikeLocals :many
SELECT id FROM "class"
WHERE "self" = @self AND "conn" = @conn AND "_row" = @_row AND "_rows" = @_rows AND "models" = @models AND "typing" = @typing
  AND "_stmt" = @_stmt AND "_out" = @_out AND "_status" = @_status AND "_n" = @_n AND "_a" = @_a AND "arg" = @arg;

-- name: SingleParamSelf :one
SELECT id FROM "class" WHERE "self" = @self;

-- name: SingleParamModels :one
SELECT "models" FROM "class" WHERE "models" = @models;

-- name: Close :one
SELECT 1 AS one;

-- name: WithTx :one
SELECT 2 AS two;

-- name: Prepare :one
SELECT 3 AS three;

-- name: Import :one
SELECT 4 AS four;

-- name: get_snake_case :one
SELECT 5 AS five;

-- name: ListHTTPURLs :many
SELECT 6 AS six;

-- name: AnonymousColumns :one
SELECT 1, 'a'::text, 2 + 2, NULL::int, id FROM "class" LIMIT 1;

-- name: DuplicateColumns :one
SELECT a.id, b.id, a.id AS id, count(*) AS count, count(*) AS count
FROM "class" a JOIN "class" b ON true GROUP BY a.id, b.id LIMIT 1;

-- name: RepeatedNamedParam :many
SELECT id FROM "class" WHERE id = @val OR "from" = @val OR "collections" = @val;

-- name: RepeatedPositional :many
SELECT id FROM "class" WHERE id = $1 OR "from" = $1;

-- name: UnnamedParams :one
SELECT $1::int + $2::int AS total;

-- name: OtherSchema :one
INSERT INTO other.things (id, e) VALUES ($1, $2) RETURNING *;

-- name: Quoting :one
SELECT '"""' || $1::text || '\' || E'\n' || E'\\' AS weird;

-- name: GetUserProfile :one
SELECT * FROM "UserProfile";

-- name: GetFirst :one
SELECT * FROM "1st table";

-- name: GetUnicode :one
SELECT * FROM "Ünïcode tâble";

-- name: List :many
SELECT id FROM "class" ORDER BY id;

-- name: Int :one
SELECT count(*)::int AS n FROM "class";

-- name: Lock :one
SELECT pg_advisory_xact_lock(42);

-- name: LockMany :many
SELECT pg_advisory_xact_lock(g) FROM generate_series(1, 2) AS g;
