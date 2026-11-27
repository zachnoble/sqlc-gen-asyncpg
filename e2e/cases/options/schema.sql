CREATE TYPE status AS ENUM ('open', 'closed', 'in-progress');
CREATE TYPE unused_enum AS ENUM ('x');

CREATE TABLE users (
  user_id    bigserial PRIMARY KEY,
  user_name  text NOT NULL,
  email_addr text,
  status     status NOT NULL DEFAULT 'open'
);

CREATE TABLE unused_things (id int PRIMARY KEY);

CREATE TABLE people (id int PRIMARY KEY, name text NOT NULL);
CREATE TABLE campus (id int PRIMARY KEY);
CREATE TABLE metadata (id int PRIMARY KEY);
CREATE TABLE news (id int PRIMARY KEY);
