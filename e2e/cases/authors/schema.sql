CREATE TYPE book_type AS ENUM ('FICTION', 'NONFICTION', 'sci-fi', 'a b');

-- Authors write books.
CREATE TABLE authors (
  id   BIGSERIAL PRIMARY KEY,
  name text      NOT NULL,
  bio  text
);
COMMENT ON TABLE authors IS 'Authors write books.';
COMMENT ON COLUMN authors.bio IS 'Optional biography.';

CREATE TABLE books (
  book_id   SERIAL PRIMARY KEY,
  author_id BIGINT NOT NULL REFERENCES authors(id),
  title     text NOT NULL,
  kind      book_type NOT NULL DEFAULT 'FICTION',
  tags      text[] NOT NULL DEFAULT '{}',
  price     numeric(10, 2)
);
