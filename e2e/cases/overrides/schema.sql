CREATE DOMAIN email AS text;
CREATE SCHEMA shop;
CREATE TABLE users (
  id          int PRIMARY KEY,
  contact     email NOT NULL,
  backup      email,
  meta        jsonb NOT NULL,
  extra       jsonb,
  label       text NOT NULL,
  note        text,
  tags        text[] NOT NULL,
  created_at  timestamptz NOT NULL,
  created_by  text NOT NULL,
  amount      numeric NOT NULL
);
CREATE TABLE shop.items (id int PRIMARY KEY, price numeric NOT NULL, created_at timestamptz NOT NULL);
