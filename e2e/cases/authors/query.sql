-- name: GetAuthor :one
SELECT * FROM authors
WHERE id = $1 LIMIT 1;

-- name: ListAuthors :many
-- Lists all authors ordered by name.
SELECT * FROM authors
ORDER BY name;

-- name: CreateAuthor :one
INSERT INTO authors (
  name, bio
) VALUES (
  $1, $2
)
RETURNING *;

-- name: DeleteAuthor :exec
DELETE FROM authors
WHERE id = $1;

-- name: UpdateBios :execrows
UPDATE authors SET bio = @bio WHERE name LIKE @pattern;

-- name: TouchAuthors :execresult
UPDATE authors SET name = name;

-- name: CreateBook :one
INSERT INTO books (author_id, title, kind, tags, price)
VALUES ($1, $2, $3, $4, $5)
RETURNING *;

-- name: BooksByKind :many
SELECT book_id, title, kind FROM books WHERE kind = $1 ORDER BY book_id;

-- name: BookKinds :many
SELECT DISTINCT kind FROM books ORDER BY kind;

-- name: BooksWithAuthor :many
SELECT sqlc.embed(books), sqlc.embed(authors)
FROM books JOIN authors ON authors.id = books.author_id
ORDER BY books.book_id;

-- name: CountAuthors :one
SELECT count(*) FROM authors;

-- name: AuthorBio :one
SELECT bio FROM authors WHERE id = $1;

-- name: AuthorsByIDs :many
SELECT id, name FROM authors WHERE id = ANY(@ids::bigint[]) ORDER BY id;

-- name: AuthorsBySlice :many
SELECT id FROM authors WHERE id IN (sqlc.slice(ids)) ORDER BY id;

-- name: AuthorsNotInSlice :many
SELECT id FROM authors WHERE id NOT IN (sqlc.slice(ids)) ORDER BY id;

-- name: SearchAuthors :many
SELECT id FROM authors
WHERE (sqlc.narg(name)::text IS NULL OR name = sqlc.narg(name))
  AND (sqlc.narg(bio)::text IS NULL OR bio = sqlc.narg(bio))
ORDER BY id;

-- name: CopyAuthors :copyfrom
INSERT INTO authors (name, bio) VALUES ($1, $2);

-- name: CopyBookTitles :copyfrom
INSERT INTO books (author_id, title, kind) VALUES (@author_id, @title, @kind);

-- name: BatchCreateAuthors :batchexec
INSERT INTO authors (name) VALUES ($1);

-- name: BatchGetAuthor :batchone
SELECT * FROM authors WHERE id = $1;

-- name: BatchBooksByAuthor :batchmany
SELECT book_id, title FROM books WHERE author_id = $1 ORDER BY book_id;

-- name: AuthorsLeftJoinBooks :many
SELECT sqlc.embed(authors), sqlc.embed(books)
FROM authors LEFT JOIN books ON books.author_id = authors.id
ORDER BY authors.id;
