# SQL Style Guide

Jarify enforces a single, non-configurable SQL style. This document describes every rule with a **bad** (input) and **good** (output) example.

---

## Formatting Rules

### Keywords — uppercase

SQL keywords are always uppercase.

**Bad**
```sql
select a, b from my_table where x > 1
```

**Good**
```sql
SELECT
   a
  ,b
FROM my_table
WHERE
  x > 1
;
```

---

### Functions — lowercase

DuckDB built-in functions are always lowercase.

**Bad**
```sql
SELECT REGEXP_EXTRACT(file, 'version=(.{21})', 1) AS version FROM GLOB('s3://bucket/*/*')
```

**Good**
```sql
SELECT
   regexp_extract(file, 'version=(.{21})', 1) AS version
FROM glob('s3://bucket/*/*')
;
```

---

### One column per line

Every item in a `SELECT` list gets its own line.

**Bad**
```sql
SELECT a, b, c FROM t
```

**Good**
```sql
SELECT
   a
  ,b
  ,c
FROM t
;
```

---

### Leading commas

Commas go at the start of each line (except the first). The first column gets one extra leading space so its content aligns with the `,col` lines.

**Bad**
```sql
SELECT
  a,
  b,
  c
FROM t
```

**Good**
```sql
SELECT
   a
  ,b
  ,c
FROM t
;
```

The same pattern applies to function arguments that wrap across lines:

**Bad**
```sql
SELECT * FROM read_parquet('data.parquet',
  hive_partitioning = TRUE,
  hive_types = {'k': text}
)
```

**Good**
```sql
SELECT
   *
FROM read_parquet(
   'data.parquet'
  ,hive_partitioning = TRUE
  ,hive_types = {'k': text}
)
;
```

---

### AND / OR conditions — one per line

Every condition in a `WHERE`, `ON`, or `HAVING` clause is on its own line.

**Bad**
```sql
SELECT a FROM t WHERE x > 1 AND y < 2 AND z = 'foo'
```

**Good**
```sql
SELECT
   a
FROM t
WHERE
  x > 1
  AND y < 2
  AND z = 'foo'
;
```

---

### CTE layout

The opening parenthesis goes on its own line. Each subsequent CTE is prefixed with a comma (no space between comma and name).

**Bad**
```sql
WITH base AS (SELECT a, b FROM foo), enriched AS (SELECT base.a, bar.c FROM base JOIN bar ON base.id = bar.id) SELECT enriched.a FROM enriched
```

**Good**
```sql
WITH base AS
(
  SELECT
     a
    ,b
  FROM foo
)
,enriched AS
(
  SELECT
     base.a
    ,bar.c
  FROM base
  INNER JOIN bar
    ON base.id = bar.id
)
SELECT
   enriched.a
FROM enriched
;
```

---

### CTE names — underscore prefix

CTE names must start with an underscore.

**Bad**
```sql
WITH latest_version AS ( ... )
SELECT * FROM latest_version
```

**Good**
```sql
WITH _latest_version AS
(
  ...
)
FROM _latest_version
;
```

---

### Table aliases — `AS` always required

The `AS` keyword is never omitted from table or column aliases.

**Bad**
```sql
SELECT a foo, b bar FROM my_table t
```

**Good**
```sql
SELECT
   a AS foo
  ,b AS bar
FROM my_table AS t
;
```

---

### Column alias alignment

When two or more columns in a `SELECT` list have aliases, the `AS` keyword is aligned to the widest column expression.

**Bad**
```sql
SELECT a AS foo, some_long_expression AS bar FROM t
```

**Good**
```sql
SELECT
   a                    AS foo
  ,some_long_expression AS bar
FROM t
;
```

---

### Bare `JOIN` → `INNER JOIN`

A `JOIN` with no explicit qualifier is normalized to `INNER JOIN`.

**Bad**
```sql
SELECT a FROM foo JOIN bar ON foo.id = bar.id
```

**Good**
```sql
SELECT
   a
FROM foo
INNER JOIN bar
  ON foo.id = bar.id
;
```

---

### `IS NOT NULL` preserved

`IS NOT NULL` is kept as-is and never rewritten to `NOT x IS NULL`.

**Bad** (what some formatters emit)
```sql
WHERE NOT end_date IS NULL
```

**Good**
```sql
WHERE
  end_date IS NOT NULL
```

---

### `NULLS LAST` — suppressed when it matches DuckDB default

DuckDB orders `ASC` columns `NULLS LAST` by default. When the explicit `NULLS LAST` matches that default it is dropped. `NULLS FIRST` (non-default) is always preserved.

**Bad**
```sql
SELECT a FROM t ORDER BY a ASC NULLS LAST
```

**Good**
```sql
SELECT
   a
FROM t
ORDER BY
   a
;
```

---

### Type casts — prefer `::` over `CAST()`

Use the concise DuckDB `::` cast syntax instead of the verbose `CAST()` form.

**Bad**
```sql
SELECT CAST(a AS INT), CAST(b AS TEXT), CAST(c AS BOOLEAN) FROM t
```

**Good**
```sql
SELECT
   a::INT
  ,b::TEXT
  ,c::BOOLEAN
FROM t
;
```

---

### `SELECT *` — rewritten as FROM-first

`SELECT *` is rewritten to DuckDB's FROM-first syntax, omitting the `SELECT` clause entirely. Applies only when there are no JOINs.

**Bad**
```sql
SELECT
   *
FROM people
;
```

**Good**
```sql
FROM people
;
```

Also applies with `WHERE`, `ORDER BY`, `LIMIT`, etc.:

```sql
FROM orders
WHERE
  status = 'active'
ORDER BY
   created_at
;
```

---

### Statement terminator

Every statement ends with a semicolon on its own line, followed by a blank line.

**Bad**
```sql
SELECT a FROM t; SELECT b FROM u;
```

**Good**
```sql
SELECT
   a
FROM t
;

SELECT
   b
FROM u
;
```

---

## Lint Rules

Lint rules report violations but do not modify the SQL. All rules default to `warn`. Severity can be set to `off`, `warn`, or `error` in `jarify.toml`.

---

### `no-select-star`

Flag `SELECT *`. `COUNT(*)` is exempt.

**Bad**
```sql
SELECT * FROM products
```

**Good**
```sql
SELECT
   id
  ,name
  ,price
FROM products
;
```

---

### `no-implicit-cross-join`

Flag comma-separated tables in `FROM` (implicit cross join). Require an explicit `CROSS JOIN` or an `ON`/`USING` clause.

**Bad**
```sql
SELECT a.x, b.y FROM a, b WHERE a.id = b.id
```

**Good**
```sql
SELECT
   a.x
  ,b.y
FROM a
INNER JOIN b
  ON a.id = b.id
;
```

---

### `no-unused-cte`

Flag CTEs that are defined but never referenced in the query body.

**Bad**
```sql
WITH unused AS (SELECT 1 AS x)
SELECT 2
```

**Good**
```sql
WITH base AS
(
  SELECT
     1 AS x
)
SELECT
   x
FROM base
;
```

---

### `duckdb-type-style`

Flag non-canonical DuckDB type names. Use the canonical form instead.

| Non-canonical | Canonical |
|---------------|-----------|
| `FLOAT`, `FLOAT4` | `REAL` |
| `NVARCHAR` | `TEXT` |

**Bad**
```sql
CREATE TABLE t (score FLOAT, label NVARCHAR)
```

**Good**
```sql
CREATE TABLE t (score REAL, label TEXT)
```

---

### `duckdb-prefer-qualify`

Flag the pattern of wrapping a window function in a subquery just to filter on its result. Use `QUALIFY` instead.

**Bad**
```sql
SELECT *
FROM (
  SELECT a, ROW_NUMBER() OVER (PARTITION BY b ORDER BY c) AS rn
  FROM t
) AS sub
WHERE rn = 1
```

**Good**
```sql
SELECT
   a
  ,row_number() OVER (PARTITION BY b ORDER BY c) AS rn
FROM t
QUALIFY
  rn = 1
;
```
