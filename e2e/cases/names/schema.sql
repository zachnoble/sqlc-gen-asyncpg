CREATE TYPE weird_enum AS ENUM ('', ' ', 'a-b', 'a_b', 'A', 'a', '1st', '_x', 'none', 'it''s', 'back\slash', 'ñ', 'value', 'name', 'mro', 'VALUE_3');

CREATE SCHEMA other;
CREATE TYPE other.weird_enum AS ENUM ('z');

CREATE TABLE "class" (
  "from" int NOT NULL,
  "def" text,
  "None" text,
  "True" boolean,
  "self" text,
  "id" int PRIMARY KEY,
  "type" text,
  "list" int[],
  "datetime" timestamp,
  "decimal" numeric,
  "uuid" uuid,
  "typing" text,
  "models" weird_enum,
  "msgspec" text,
  "asyncpg" int4range,
  "ipaddress" inet,
  "collections" int,
  "enum" weird_enum,
  "conn" text,
  "arg" text,
  "args" text,
  "_row" text,
  "_rows" text,
  "_stmt" text,
  "_out" text,
  "_status" text,
  "_n" text,
  "_a" text,
  "_records" text,
  "first name" text,
  "first_name" text,
  "2fa" boolean,
  "café" text,
  "Name" text,
  "name" text,
  "__secret" text,
  "WeirdEnum" weird_enum,
  "OtherWeirdEnum" other.weird_enum
);

CREATE TABLE "UserProfile" (id int PRIMARY KEY);
CREATE TABLE "1st table" (id int PRIMARY KEY);
CREATE TABLE "Ünïcode tâble" (id int PRIMARY KEY);
CREATE TABLE other.things (id int PRIMARY KEY, e other.weird_enum NOT NULL);
