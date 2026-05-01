# SQL Style Guide

Jarify enforces a single, non-configurable SQL style. This document describes every rule with a **bad** (input) and **good** (output) example.

---

## Formatting Rules

### Keywords — uppercase; data types — lowercase

SQL keywords (`SELECT`, `FROM`, `WHERE`, `JOIN`, `NOT NULL`, etc.) are always uppercase. Data type names (`text`, `int`, `timestamp`, `decimal`, etc.) are always lowercase.

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
WHERE x > 1
;
```

Type names are lowercased even in casts and `CREATE TABLE`:

**Bad**
```sql
SELECT a::TEXT, b::INTEGER FROM t
CREATE TABLE t (id INTEGER NOT NULL, name TEXT)
```

**Good**
```sql
SELECT
   a::text
  ,b::int
FROM t
;

CREATE TABLE t
(
   id   int  NOT NULL
  ,name text
)
;
```

---

### Boolean literals — lowercase

Boolean literals are always lowercase: `true` and `false`.

**Bad**
```sql
SELECT a FROM t WHERE a.active = TRUE AND a.deleted = FALSE
```

**Good**
```sql
SELECT
   a
FROM t
WHERE a.active = true
  AND a.deleted = false
;
```

---

### Functions — aggregate and window uppercase, scalar lowercase

Aggregate and window functions (`COUNT`, `SUM`, `AVG`, `ROW_NUMBER`, `RANK`, `LEAD`, etc.) are always uppercase. All other DuckDB built-in functions (`regexp_extract`, `strftime`, `date_trunc`, etc.) remain lowercase. User-defined macro and function names are preserved and must not be rewritten to a different built-in name.

**Bad**
```sql
SELECT COUNT(*), SUM(amount), row_number() OVER (ORDER BY ts), REGEXP_EXTRACT(x, '[0-9]+'), STRFTIME(ts, '%Y') FROM t
```

**Good**
```sql
SELECT
   COUNT(*)
  ,SUM(amount)
  ,ROW_NUMBER() OVER (ORDER BY ts)
  ,regexp_extract(x, '[0-9]+')
  ,strftime(ts, '%Y')
FROM t
;
```

---

### Built-in function aliases — canonical DuckDB names

Built-in aliases are normalized to jarify's canonical DuckDB names. In practice that means `listagg(...)` becomes `STRING_AGG(...)`, and `array_contains(...)` becomes `list_contains(...)`.

**Bad**
```sql
SELECT listagg(code, ' | ') AS codes, array_contains(tags, 'x') AS has_tag FROM t
```

**Good**
```sql
SELECT
   STRING_AGG(code, ' | ')  AS codes
  ,list_contains(tags, 'x') AS has_tag
FROM t
;
```

---

### Two-argument null fallback — prefer `ifnull()`

Use `ifnull(x, y)` for the two-argument null-fallback case. `coalesce(...)` stays in place when there are three or more arguments.

**Bad**
```sql
SELECT COALESCE(a, b) AS two_arg, COALESCE(c, d) AS two_arg_upper, COALESCE(a, b, c) AS three_arg FROM t
```

**Good**
```sql
SELECT
   ifnull(a, b)      AS two_arg
  ,ifnull(c, d)      AS two_arg_upper
  ,coalesce(a, b, c) AS three_arg
FROM t
;
```

---

### Custom macros — preserve original names

User-defined macro and function names keep their original identifier instead of being rewritten to a DuckDB built-in alias. Jarify still normalizes casing for scalar-style calls.

**Bad**
```sql
SELECT TRANSFORM(t, _transform) FROM txns
```

**Good**
```sql
SELECT
   transform(t, _transform)
FROM txns
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

### WHERE / HAVING — first condition inline, AND/OR aligned

The first condition goes on the same line as the keyword. Each subsequent `AND`/`OR` connector is right-justified so all condition content starts at the same column (`WHERE ` = 6 chars, `HAVING ` = 7 chars).

**Bad**
```sql
SELECT a FROM t WHERE x > 1 AND y < 2 OR z = 'foo'
```

**Good**
```sql
SELECT
   a
FROM t
WHERE x > 1
  AND y < 2
   OR z = 'foo'
;
```

Single-condition `WHERE` is also inline:

```sql
FROM orders
WHERE status = 'active'
;
```

The same inline rule applies to `HAVING`:

```sql
SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY
   a
HAVING COUNT(*) > 1
   AND a IS NOT NULL
;
```

---

### WHERE — `=` operator column alignment

When a `WHERE` clause contains two or more equality (`=`) comparisons anywhere in the condition tree, the left-hand sides of all **top-level** `AND` equality conditions are right-padded so that the `=` signs align vertically. The target column is the longest LHS (across all `=` in the clause, including nested ones) plus one space.

Parenthesised compound conditions (e.g. `(a = b OR c IS NULL)`) that appear as direct `AND` operands are kept on a single line.

**Bad**
```sql
WHERE type = _property_type
  AND level_type = _property_level_type
```

**Good**
```sql
WHERE type       = _property_type
  AND level_type = _property_level_type
```

---

### WHERE — `IN (subquery)` layout

When the full `col IN (SELECT ...)` expression fits on one line within the configured max line length, it stays inline. When it would exceed the threshold, the `(` goes on its own line, the inner query is indented by one level, and `)` closes at the same column as `IN`.

**Bad**
```sql
WHERE program_key IN (
    SELECT
       program_key
    FROM _programs
  )
```

**Good — short subquery stays inline**
```sql
WHERE program_key IN (SELECT program_key FROM _programs)
```

**Good — long subquery expands to block form**
```sql
WHERE program_key IN
(
  SELECT
     program_key
  FROM _programs
  WHERE some_very_long_column = 'some_very_long_value_that_exceeds_the_line_length'
)
```

---

### `GROUP BY` — one expression per line

Every `GROUP BY` expression is on its own line using the same leading-comma style as `SELECT`. `GROUP BY ALL` is exempt and stays on one line.

**Bad**
```sql
SELECT a, b, COUNT(*) FROM t GROUP BY a, b
```

**Good**
```sql
SELECT
   a
  ,b
  ,COUNT(*)
FROM t
GROUP BY
   a
  ,b
;
```

`GROUP BY ALL` (DuckDB shorthand) stays inline:

```sql
SELECT
   a
  ,b
  ,COUNT(*)
FROM t
GROUP BY ALL
;
```

---

### `ORDER BY` — one expression per line, except `ORDER BY ALL`

Every explicit `ORDER BY` expression is on its own line using the same leading-comma style as `SELECT`. DuckDB's `ORDER BY ALL` shorthand is exempt and stays on one line.

**Bad**
```sql
FROM data
ORDER BY
   ALL
```

**Good**
```sql
FROM data
ORDER BY ALL
;
```

Explicit sort keys still wrap one per line:

```sql
SELECT
   a
  ,b
FROM data
ORDER BY
   a
  ,b DESC
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
  INNER JOIN bar ON base.id = bar.id
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

### CTE inline comments — after `AS`

Inline comments on a CTE definition are placed after `AS` on the same line, using `--` style. The opening `(` still goes on its own line below.

**Bad**
```sql
WITH _programs /* this is where we filter */ AS
(
  SELECT ...
)
```

**Good**
```sql
WITH _programs AS -- this is where we filter by parameters
(
  SELECT ...
)
```

---

### Predicate comments — keep `OR` / `AND` outside the comment

A comment that documents one branch of a boolean expression stays on its own line before that branch. Jarify must not collapse the comment and the following `OR` / `AND` onto one line.

**Bad**
```sql
WHERE 1 = 1
  AND ((a = 1) -- note OR b = 2)
```

**Good**
```sql
WHERE 1 = 1
  AND (
    -- note
    (a = 1)
    OR b = 2
  )
```

---

### Table aliases — `AS` omitted in `FROM`/`JOIN`, required in `SELECT`

The `AS` keyword is kept for column aliases in `SELECT` lists but **omitted** between a table reference and its alias in `FROM` and `JOIN` lines.

**Bad**
```sql
SELECT a foo, b bar FROM my_table t
```

**Good**
```sql
SELECT
   a AS foo
  ,b AS bar
FROM my_table t
;
```

This applies equally to **table-function aliases** such as `UNNEST`. The `AS` keyword is dropped before the alias and any named column list.

**Bad**
```sql
SELECT o.* FROM offers o CROSS JOIN UNNEST(o.vals) AS t(v)
```

**Good**
```sql
SELECT
   o.*
FROM offers o
CROSS JOIN UNNEST(o.vals) t(v)
;
```

---

### Column alias alignment

When a query contains two or more column aliases anywhere in its query-wide `SELECT` lists, the `AS` keyword is aligned to one visible column across the full query. That includes the outer query plus CTE bodies, including nested CTEs, even when those `SELECT` lists are indented at different depths. Multi-line expressions still participate — the closing line (for example `END`) is padded so its trailing `AS` lines up with neighboring single-line aliases.

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

**Also good**
```sql
SELECT
   foo_bar_baz AS xyz
  ,CASE
     WHEN foo
     THEN bar
     ELSE NULL
   END        AS abc
FROM data
;
```

**Also good**
```sql
WITH _a AS
(
  SELECT
     x   AS first
    ,yy  AS second
  FROM t
)
,_b AS
(
  SELECT
     zzz AS third
    ,w   AS fourth
  FROM u
)
SELECT
   q   AS fifth
  ,rr  AS sixth
FROM _a
INNER JOIN _b ON 1 = 1
;
```

**Also good**
```sql
WITH _outer_group AS
(
  WITH seed_group AS
  (
    SELECT
       alpha_value       AS seed_one
      ,beta_metric       AS seed_two
    FROM source_a
  )
  SELECT
     seed_one           AS outer_one
    ,seed_two           AS outer_two
  FROM seed_group
)
,_sibling_group AS
(
  SELECT
     gamma_code         AS sibling_one
    ,delta_indicator    AS sibling_two
  FROM source_b
)
SELECT
   outer_one           AS final_one
  ,sibling_two         AS final_two
FROM _outer_group
INNER JOIN _sibling_group ON outer_one = sibling_one
;
```

---

### `JOIN` formatting — inline `ON`, aligned aliases

When a `FROM`/`JOIN` block contains only simple table references and/or `UNNEST` table-function calls, aliases are **start-aligned** — every alias begins at the same column (determined by the widest `keyword + table_ref` in the block).

**Bad**
```sql
SELECT a FROM orders AS o LEFT JOIN users AS u ON u.id = o.user_id LEFT JOIN addresses AS addr ON addr.id = o.aid
```

**Good**
```sql
SELECT
   a
FROM orders          o
LEFT JOIN users      u ON u.id = o.user_id
LEFT JOIN addresses addr ON addr.id = o.aid
;
```

`UNNEST` table-function calls participate in the same alignment:

```sql
SELECT
   o.*
FROM offers                          o
CROSS JOIN UNNEST(o.group_by_values) gbv(group_by_value)
;
```

If any entry in the block is a subquery (multi-line), alignment is skipped for the entire block, but `ON` is still kept inline.

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
INNER JOIN bar ON foo.id = bar.id
;
```

---

### `LEFT OUTER JOIN` → `LEFT JOIN`

The redundant `OUTER` keyword is dropped from `LEFT` and `RIGHT` joins. `FULL OUTER JOIN` is preserved.

**Bad**
```sql
SELECT a FROM foo LEFT OUTER JOIN bar ON foo.id = bar.id
```

**Good**
```sql
SELECT
   a
FROM foo
LEFT JOIN bar ON foo.id = bar.id
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
WHERE end_date IS NOT NULL
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
   a::int
  ,b::text
  ,c::boolean
FROM t
;
```

---

### JSON extraction casts — preserve grouping

When converting `CAST(json_expr->'path' AS type)` or `CAST(json_expr->>'path' AS type)` to DuckDB shorthand, keep parentheses around the extraction so the cast applies to the extracted value rather than the JSON path literal.

**Bad**
```sql
SELECT j->'x'::STRUCT(a INTEGER), j->>'label'::TEXT FROM t
```

**Good**
```sql
SELECT
   (j->'x')::struct(a int)
  ,(j->>'label')::text
FROM t
;
```

---

### Dynamic JSON paths — keep function syntax

Use `->` and `->>` only for static JSON paths. When the path is built from an expression such as `concat(...)`, preserve `json_extract(...)` / `json_extract_string(...)` so formatting does not change runtime behavior.

**Bad**
```sql
SELECT to_json({'purchaser': ft.purchaser})->>concat('$.', o.group_by_field, '.', o.group_by_key) FROM offers o JOIN fact_transactions ft ON o.id = ft.offer_id
```

**Good**
```sql
SELECT
   json_extract_string(to_json({'purchaser': ft.purchaser}), concat('$.', o.group_by_field, '.', o.group_by_key))
FROM offers             o
INNER JOIN fact_transactions ft ON o.id = ft.offer_id
;
```

---

### Struct literal — leading-comma style when multi-line

When a positional struct literal `(val1, val2, ...)::my_struct` wraps across lines, the opening `(` appears on its own line and the fields use the same leading-comma style as `SELECT` lists.

**Bad**
```sql
SELECT (active_ingredient_key, quantity, active_ingredient_uom_key)::active_ingredient_struct FROM sku_composition
```

**Good**
```sql
SELECT
   (
     active_ingredient_key
    ,quantity
    ,active_ingredient_uom_key
  )::active_ingredient_struct
FROM sku_composition
;
```

---

### `DISTINCT` inside aggregates — own line when wrapping

When `ARRAY_AGG(DISTINCT expr ...)` wraps across lines, `DISTINCT` appears on its own line.

**Bad**
```sql
SELECT ARRAY_AGG(DISTINCT (active_ingredient_key, quantity, uom_key)::active_ingredient_struct) FROM t
```

**Good**
```sql
SELECT
   ARRAY_AGG(
    DISTINCT (
       active_ingredient_key
      ,quantity
      ,uom_key
    )::active_ingredient_struct
  )
FROM t
;
```

---

### `CASE` — always multi-line

`CASE` expressions are always formatted across multiple lines in pretty mode, regardless of branch count or line length.

- **Simple CASE** (`CASE expr WHEN lit THEN val`) keeps `WHEN … THEN` on one line, and `THEN` values are column-aligned when all branches fit on a single line.
- **Searched CASE** (`CASE WHEN cond THEN val`) puts `THEN` on its own line. Multi-line boolean conditions keep `AND` / `OR` on their own lines under `WHEN`, with `AND` / `OR` right-aligned as in the issue #260 examples.

**Bad** (flattened to one line)
```sql
SELECT CASE o.part WHEN 'AND' THEN '&&' WHEN 'OR' THEN '||' WHEN 'NOT' THEN '!' ELSE ifnull(qr.met::text, o.part) END AS expr
FROM data
```

**Good** (simple CASE)
```sql
SELECT
   *
  ,CASE o.part
    WHEN 'AND' THEN '&&'
    WHEN 'OR'  THEN '||'
    WHEN 'NOT' THEN '!'
    ELSE ifnull(qr.met::text, o.part)
  END AS expr
FROM data
```

**Also good** (searched CASE)
```sql
SELECT
   foo_bar_baz AS xyz
  ,CASE
     WHEN foo
     THEN bar
     WHEN baz
      AND baq
     THEN world
     ELSE NULL
   END        AS abc
FROM data
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
WHERE status = 'active'
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

### `CREATE TABLE` layout

The opening parenthesis goes on its own line. Column names are padded to align all type tokens, and types are padded to align all constraint tokens when any column carries constraints. A blank line separates column definitions from table-level constraints (`PRIMARY KEY`, `UNIQUE`, `CHECK`, etc.).

**Bad**
```sql
CREATE OR REPLACE TABLE examples (
   transaction_id TEXT NOT NULL,
   program_supplier_key TEXT NOT NULL,
   seller_key TEXT,
   PRIMARY KEY (program_supplier_key, transaction_id)
)
```

**Good**
```sql
CREATE OR REPLACE TABLE examples
(
   transaction_id       text NOT NULL
  ,program_supplier_key text NOT NULL
  ,seller_key           text

  ,PRIMARY KEY (program_supplier_key, transaction_id)
)
;
```

---

### `CREATE MACRO` layout

The opening parenthesis of the parameter list goes on its own line. Parameters use the standard leading-comma style: the first parameter is indented three spaces, subsequent parameters use two spaces plus a leading comma.

**Bad**
```sql
CREATE OR REPLACE MACRO get_programs_json(_participant_key, _time_frame, _program_supplier_key) AS (SELECT 1)
```

**Good**
```sql
CREATE OR REPLACE MACRO get_programs_json
(
   _participant_key
  ,_time_frame
  ,_program_supplier_key
) AS
(
  SELECT 1
)
;
```

---

### `VALUES` CTE layout

A `WITH` clause CTE whose body is a plain `VALUES` list is rendered as `VALUES` (not `FROM (VALUES ...) AS ...`). Rows use leading-comma style. Each non-last column is right-padded with spaces after its comma so that the next column aligns across all rows. CTE names that declare column aliases include a space before the column list.

**Bad**
```sql
WITH _lookup (code, label) AS (VALUES ('a', 'active'), ('i', 'inactive'))
SELECT code, label FROM _lookup
```

**Good**
```sql
WITH _lookup (code, label) AS
(
  VALUES
     ('a', 'active'  )
    ,('i', 'inactive')
)
SELECT
   code
  ,label
FROM _lookup
;
```

---

## Lint Rules

Rules in this section may lint only, auto-fix during `fmt`, or do both. All rules default to `warn`. Severity can be set to `off`, `warn`, or `error` in `jarify.toml`.

### Comment overrides

Use `jarify` comment directives when one line or region needs an exception without changing repo-wide config.

Supported directives:

- `-- jarify: disable-line <rule>` — disable a rule on the current line
- `-- jarify: disable-next-line <rule>` — disable a rule on the following line
- `-- jarify: disable <rule>` / `-- jarify: enable <rule>` — disable a rule for a region
- `-- jarify: disable-file <rule>` — disable a rule for the whole file
- `-- jarify: set max_line_length = 140` / `-- jarify: reset max_line_length` — override line length for following statements until reset

Rules use their lint names such as `no-select-star`, `cte-naming`, or `prefer-if-over-case`.

**Example**
```sql
-- jarify: disable-next-line prefer-if-over-case
SELECT CASE WHEN is_large THEN 'big' ELSE 'small' END FROM sizes
```

**Good output**
```sql
-- jarify: disable-next-line prefer-if-over-case
SELECT
   CASE
     WHEN is_large
     THEN 'big'
     ELSE 'small'
   END
FROM sizes
;
```

---

### `no-select-star`

Flag top-level `SELECT *` and `table.*` in `SELECT` lists. `COUNT(*)` is exempt.

When `prefer_from_first = true` (the default), single-table `SELECT *` queries are not flagged because the formatter already rewrites them to FROM-first syntax (`FROM t`). The rule still fires for `SELECT *` with JOINs, since those are not rewritten.

**Bad** (with `prefer_from_first = false`)
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

**Also good** (formatter rewrites `SELECT * FROM products` to this when `prefer_from_first = true`)
```sql
FROM products
;
```

---

### `no-implicit-cross-join`

**Auto-fixed by `fmt`.** Rewrite comma-separated tables in `FROM` to explicit `CROSS JOIN`, and flag the pattern when linting.

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
CROSS JOIN b
WHERE a.id = b.id
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
| `float`, `float4` | `real` |
| `varchar`, `nvarchar` | `text` |

**Bad**
```sql
CREATE TABLE t (score FLOAT, short_label VARCHAR, long_label NVARCHAR)
```

**Good**
```sql
CREATE TABLE t (score real, short_label text, long_label text)
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
  ,ROW_NUMBER() OVER (PARTITION BY b ORDER BY c) AS rn
FROM t
QUALIFY
  rn = 1
;
```

---

### `prefer-group-by-all`

**Auto-fixed by `fmt`.** Rewrites explicit `GROUP BY col1, col2, ...` to `GROUP BY ALL` when every standalone non-aggregate `SELECT` expression is listed. Mixed aggregate/non-aggregate expressions stay explicit because DuckDB can reject `GROUP BY ALL` for that shape.

**Bad**
```sql
SELECT a, b, COUNT(*) AS n FROM t GROUP BY a, b
```

**Good**
```sql
SELECT
   a
  ,b
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
;
```

---

### `prefer-using-over-on`

Flag `ON a.col = b.col` equi-joins where both sides reference the same column name. Use `USING (col)` instead.

**Bad**
```sql
SELECT a.x FROM a INNER JOIN b ON a.id = b.id
```

**Good**
```sql
SELECT
   a.x
FROM a
INNER JOIN b USING (id)
;
```

---

### `consistent-empty-array`

Flag `'[]'::type[]` (string-cast empty arrays) in favour of the native DuckDB `[]` empty array literal.

**Bad**
```sql
SELECT COALESCE(tags, '[]')::text[] AS tags FROM t
```

**Good**
```sql
SELECT
   ifnull(tags, [])::text[] AS tags
FROM t
;
```

---

### `no-select-star-in-cte`

Flag `SELECT *` inside CTE body definitions. Stricter variant of `no-select-star` that applies only within CTE bodies.

**Bad**
```sql
WITH _base AS (SELECT * FROM source_table)
SELECT id FROM _base
```

**Good**
```sql
WITH _base AS
(
  SELECT
     id
    ,name
  FROM source_table
)
SELECT
   id
FROM _base
;
```

---

### `prefer-neq-operator`

**Auto-fixed by `fmt`.** Always use `!=` for inequality comparisons instead of the SQL-92 `<>` operator. Both are valid in DuckDB, but `!=` is the modern standard.

**Bad**
```sql
SELECT a
FROM t
WHERE x <> y
```

**Good**
```sql
SELECT
   a
FROM t
WHERE x != y
;
```

---

### `prefer-if-over-case`

**Auto-fixed by `fmt`.** Rewrite single-branch `CASE WHEN … THEN … [ELSE …] END` expressions to DuckDB's `IF(condition, true_val, false_val)` function. The IF form is shorter and more idiomatic for simple conditionals.

Applies only to *searched* CASE with exactly one WHEN branch. Multi-branch CASE and simple CASE (`CASE expr WHEN lit …`) are left unchanged. When the original `CASE` has no `ELSE`, jarify emits an explicit `NULL` third argument because DuckDB's `IF()` requires three arguments.

**Bad**
```sql
SELECT
   CASE WHEN a > 1 THEN 'big' ELSE 'small' END AS size
  ,CASE WHEN b IS NULL THEN 0 END AS b_or_zero
FROM t
```

**Good**
```sql
SELECT
   if(a > 1, 'big', 'small') AS size
  ,if(b IS NULL, 0, NULL)    AS b_or_zero
FROM t
;
```

When a compact `if(cond, then, else)` call exceeds `max_line_length`, expand the outer
`if()` call across multiple lines. Keep the condition compact on one line, but let an
overlong `true` or `false` branch use its normal nested wrapping.

**Wide**
```sql
SELECT
   if(
      condition_that_makes_the_call_too_wide
     ,(
         very_long_value_a
        ,very_long_value_b
        ,very_long_value_c
      )::some_type
     ,fallback_value
  ) AS result
;
```
