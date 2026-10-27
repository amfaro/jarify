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

Aggregate and window functions (`COUNT`, `SUM`, `AVG`, `ROW_NUMBER`, `RANK`, `LEAD`, etc.) are always uppercase. All other DuckDB built-in functions (`regexp_extract`, `strftime`, `date_trunc`, etc.) remain lowercase. User-defined macro and function names are preserved and must not be rewritten to a different built-in name. To change the case of specific names, see [Function case overrides](#function-case-overrides) below.

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

### Function case overrides

Two config lists override the built-in classification above for specific function names. `uppercase-functions` always writes a name uppercase, and `lowercase-functions` always writes it lowercase, whichever case Jarify would otherwise use. Names match case-insensitively. Both lists default to empty, which leaves the output unchanged.

An override applies to the function name as Jarify finally writes it, so it also covers canonical renames: `list` in `uppercase-functions` turns `array_agg(x)` into `LIST(x)`, and `string_agg` in `lowercase-functions` turns `listagg(x, ',')` into `string_agg(x, ',')`. User-defined macro and function calls keep the default lowercase unless listed. Schema-qualified calls such as `main.my_macro(x)` and SQLMesh `@macro(...)` calls are never changed.

Listing a name in both lists is a config error. A list in a project `jarify.toml` replaces the same list from global config instead of extending it. If the project lists a name that global config puts in the other list, the project wins and the name is dropped from the global list. `-- jarify: set` comment directives can't set these lists.

Project config example:

```toml
[jarify]
uppercase-functions = ["list"]
lowercase-functions = ["any_value"]
```

**Bad**
```sql
SELECT string_agg(a, ',') AS s, any_value(b) AS v, array_agg(c) AS l, lag(d) OVER () AS lg, regexp_extract(x, 'y') AS r FROM t
```

**Good** (with the config above; by default `any_value` is uppercase and `list` lowercase)
```sql
SELECT
   STRING_AGG(a, ',')     AS s
  ,any_value(b)           AS v
  ,LIST(c)                AS l
  ,LAG(d) OVER ()         AS lg
  ,regexp_extract(x, 'y') AS r
FROM t
;
```

---

### Built-in function aliases — canonical DuckDB names

Built-in aliases are normalized to jarify's canonical DuckDB names. In practice that means `listagg(...)` becomes `STRING_AGG(...)`, and `array_contains(...)` becomes `list_contains(...)`. `array_agg(...)` is also normalized — see below.

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

### `array_agg()` → `list()` — canonical DuckDB aggregate

In DuckDB, `list()` is the canonical aggregate function; `array_agg()` is an alias. Jarify rewrites all `array_agg(...)` calls to `list(...)` regardless of arguments.

**Bad**
```sql
SELECT array_agg(x) FROM t;
SELECT array_agg(x ORDER BY y) FROM t;
SELECT array_agg(DISTINCT x) FROM t GROUP BY z;
```

**Good**
```sql
SELECT
   list(x)
FROM t
;
SELECT
   list(x ORDER BY y)
FROM t
;
SELECT
   list(DISTINCT x)
FROM t
GROUP BY
   z
;
```

---

### Two-argument null fallback — prefer `ifnull()`

Rule: `prefer-ifnull-over-coalesce`

Use `ifnull(x, y)` for the two-argument null-fallback case. `coalesce(...)` stays in place when there are three or more arguments. Only calls are rewritten: `IFNULL` written in a comment or a string literal keeps its text, as do `NUMERIC` and other words jarify rewrites in code.

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

User-defined macro and function names keep their original identifier instead of being rewritten to a DuckDB built-in alias. Jarify still normalizes casing for scalar-style calls; list a macro name in [`uppercase-functions`](#function-case-overrides) to write it uppercase.

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

A comment on its own line between two items lines up with the commas, and one above the first item lines up with its text. This holds in every leading-comma list: a `SELECT` list, wrapped function arguments, an `IN (…)` list, a struct literal and `VALUES` rows.

**Good**
```sql
SELECT
   -- the key first
   a
  -- b is optional
  ,b
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

A multi-line left-hand side, such as a `CASE`, isn't padded and doesn't count toward the target column.

Parenthesised compound conditions (e.g. `(a = b OR c IS NULL)`) that appear as direct `AND` operands are kept on a single line, unless they hold a comment or a `CASE`.

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

When the full `col IN (SELECT ...)` expression fits on one line within the configured max line length, it stays inline. When it would exceed the threshold, or the subquery contains a comment, a `CASE` or a `WITH`, the `(` goes on its own line, the inner query is indented by one level, and `)` closes at the same column as `IN`. (A `--` comment on the inline form would comment out the rest of the line, a `CASE` is always multi-line, and a `WITH` lays out its CTEs as at the top level; for the same reasons a `FROM (subquery)` holding any of them is never collapsed onto one line.)

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

### WHERE — `IN (…)` value list layout

When the full `col IN (a, b, …)` expression fits on one line within the configured max line length, it stays inline. When it would exceed the threshold, or a value carries a comment or holds a `CASE`, the values go one per line in leading-comma style, like wrapped function arguments: `IN (` ends its line, and `)` gets a line of its own, lined up with the start of the line that holds `IN (`. The same layout applies to an `IN` list in a `SELECT` list or a `PIVOT`, and a long list literal (`[…]`) wraps the same way.

**Bad**
```sql
SELECT rec_id FROM recs WHERE client_id = 1 AND rec_status_key IN ('nom_status_denied', 'nom_status_draft', 'nom_status_expired_draft', 'nom_status_pending_approval', 'nom_status_terminated')
```

**Good — long list puts one value per line**
```sql
SELECT
   rec_id
FROM recs
WHERE client_id = 1
  AND rec_status_key IN (
     'nom_status_denied'
    ,'nom_status_draft'
    ,'nom_status_expired_draft'
    ,'nom_status_pending_approval'
    ,'nom_status_terminated'
  )
;
```

**Good — short list stays inline**
```sql
WHERE rec_status_key IN ('nom_status_denied', 'nom_status_draft')
```

After `OR`, a wrapped list is laid out as after `AND`: its values and `)` move right with the connector, so `)` lines up under the `OR`. The same goes for the block form of an `IN (subquery)`, and for a condition after `OR` or `AND` in `HAVING`, in a commented `JOIN … ON` and under a `CASE`'s `WHEN`.

**Bad**
```sql
WHERE client_id = 1
   OR rec_status_key IN (
   'nom_status_denied'
  ,'nom_status_draft'
  ,'nom_status_expired_draft'
  ,'nom_status_pending_approval'
  ,'nom_status_terminated'
)
```

**Good**
```sql
WHERE client_id = 1
   OR rec_status_key IN (
      'nom_status_denied'
     ,'nom_status_draft'
     ,'nom_status_expired_draft'
     ,'nom_status_pending_approval'
     ,'nom_status_terminated'
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

### Window specs — one clause per line when wrapping

A window spec stays on one line when it fits. When it doesn't, each clause (`PARTITION BY`, `ORDER BY`, the frame) goes on its own line, with no commas between them. A `PARTITION BY` or `ORDER BY` list that still doesn't fit on its line puts one expression per line in leading-comma style, like a query's `ORDER BY`.

**Bad**
```sql
SELECT SUM(a.allocation_per_year / 12) OVER (PARTITION BY a.client_id, a.nomination_application_ids, a.employee_user_id ORDER BY m.the_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running FROM a
```

**Good**
```sql
SELECT
   SUM(a.allocation_per_year / 12) OVER (
     PARTITION BY a.client_id, a.nomination_application_ids, a.employee_user_id
     ORDER BY m.the_month
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running
FROM a
;
```

**Good — a list too long for its line**
```sql
SELECT
   ROW_NUMBER() OVER (
     ORDER BY
        time_frame_key
       ,client_name
       ,process_type
       ,process_sub_type
       ,audience
       ,nom_detail_status_keys
       ,nom_status_key
       ,nom_team_status_key
       ,points_actually_awarded
  ) AS node_id
FROM t
;
```

A `CASE` never fits on a line, so a window whose `PARTITION BY` or `ORDER BY` holds one is wrapped too, with that list one key per line and the CASE laid out under its keyword (see [`CASE` — always multi-line](#case--always-multi-line)).

**Bad**
```sql
SELECT
   ROW_NUMBER() OVER (PARTITION BY a ORDER BY CASE
     WHEN x = 1
     THEN 'one'
     WHEN x = 2
     THEN 'two'
     ELSE 'many'
   END) AS n
FROM t
```

**Good**
```sql
SELECT
   ROW_NUMBER() OVER (
     PARTITION BY a
     ORDER BY
        CASE
          WHEN x = 1
          THEN 'one'
          WHEN x = 2
          THEN 'two'
          ELSE 'many'
        END
  ) AS n
FROM t
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

A subquery that holds a `WITH` lays out its CTEs the same way, wherever it appears: in `FROM` or `IN (…)`, in parentheses, in a `WHERE`, `HAVING` or `JOIN … ON` condition, as a function or `if()` argument, or in a `CASE`. It never fits on one line, so whatever holds it takes the multi-line form it takes for a subquery too long for one line.

**Bad** (the CTE is squeezed onto the condition's line)
```sql
SELECT
   a
FROM t
WHERE (a IN (WITH _c AS
(SELECT a FROM u) SELECT a FROM _c) OR b)
;
```

**Good**
```sql
SELECT
   a
FROM t
WHERE (
  a IN
  (
    WITH _c AS
    (
      SELECT
         a
      FROM u
    )
    SELECT
       a
    FROM _c
  )
  OR b
)
;
```

**Also good** (as an `if()` argument)
```sql
SELECT
   if(
      x
     ,(
        WITH _c AS
        (
          SELECT
             a
          FROM u
        )
        SELECT
           MAX(a)
        FROM _c
      )
     ,0
  ) AS v
FROM t
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

Inline comments on a CTE definition are placed after `AS` on the same line, using `--` style. The opening `(` still goes on its own line below. A comment written between `AS` (or `MATERIALIZED`) and the opening `(` goes there too, even one on its own line.

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

Only one `--` comment fits after `AS`, because it runs to the end of the line. When a CTE carries several comments, they all go above the CTE, one per line, where own-line comments above a CTE already stay.

**Bad**
```sql
,_reverse_sorted AS -- rev_seq comes from seq, so rows that still tie -- can't pair the two differently between builds.
(
  SELECT ...
)
```

**Good**
```sql
-- rev_seq comes from seq, so rows that still tie
-- can't pair the two differently between builds.
,_reverse_sorted AS
(
  SELECT ...
)
```

A comment on its own line at the end of a CTE body, after its last clause, stays there, before the closing `)`. It doesn't move above the CTE or the statement.

**Bad** (the second comment no longer follows the first)
```sql
-- because we only keep track of last_visit_at
WITH _tf AS
(
  FROM time_frames
  WHERE time_frame_key IN ('current_month', 'trailing_12_months') -- only time frames that end today or later
)
```

**Good**
```sql
WITH _tf AS
(
  FROM time_frames
  WHERE time_frame_key IN ('current_month', 'trailing_12_months') -- only time frames that end today or later
  -- because we only keep track of last_visit_at
)
```

The same goes for a subquery in `FROM` or `JOIN`: a comment on its own line before its closing `)` stays at the end of its body. A subquery that holds a `WITH` lays out its CTEs as at the top level (see [CTE layout](#cte-layout)).

**Bad** (the comment is dropped, and the CTE is squeezed onto the subquery's line)
```sql
SELECT
   s.a
FROM (WITH _c AS
(SELECT a FROM t) SELECT a FROM _c) AS s
;
```

**Good**
```sql
SELECT
   s.a
FROM (
  WITH _c AS
  (
    SELECT
       a
    FROM t
  )
  SELECT
     a
  FROM _c
  -- keeps every row
) AS s
;
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

The same holds for comments on the top-level branches of `WHERE`, `HAVING`, `QUALIFY`, `JOIN … ON` and `CASE WHEN` conditions. A trailing comment stays at the end of its branch's line. A comment on its own line before `AND` / `OR` stays on its own line, aligned with that `AND` / `OR`; a comment written after the `AND` / `OR`, on its line or on the next, moves to its own line above it.

**Bad** (comments dropped, or `OR` commented out)
```sql
WHERE a IS NOT NULL
   OR b IS NOT NULL
   OR c > 0
```

**Good**
```sql
WHERE a IS NOT NULL -- has a
   -- b only matters when a is missing
   OR b IS NOT NULL
   OR c > 0 -- fallback
```

The first condition shares its line with `WHERE`, `HAVING` or `JOIN … ON`, so a comment written before it goes on its own line above that line, where a comment written on the `WHERE` line also goes. `QUALIFY` puts its condition on the next line, so the comment stays between `QUALIFY` and the condition. Inside parentheses, a comment before the first branch stays on its own line after the `(`, as in the first example.

**Bad** (the comment lands inside the condition)
```sql
WHERE a /* only active rows */ = 1
  AND b                        = 2
```

**Good**
```sql
-- only active rows
WHERE a = 1
  AND b = 2
```

A comment on the keyword itself goes above the line too: one written on or above the `WHERE`, `HAVING`, `QUALIFY` or `WINDOW` line goes above that clause, and one written before or after a join's `ON` or `USING` goes above the join. So does one after `UNION ALL`, above the `UNION ALL` line. A comment after `NOT` stays after it, as a `/* */` block comment, since the condition follows on its line. Where jarify writes `NOT` after the operand, as in `a NOT IN (…)` or `a IS NOT NULL`, the comment goes at the end of the condition.

**Bad** (the comments are dropped)
```sql
SELECT
   a
FROM t
INNER JOIN u ON u.id = t.id
WHERE NOT a
QUALIFY
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC) = 1
;
```

**Good**
```sql
SELECT
   a
FROM t
-- same id
INNER JOIN u ON u.id = t.id
WHERE NOT /* archived */ a
-- latest first
QUALIFY
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC) = 1
;
```

A comment written on a word of a predicate's operator stays after that word, as a `/* */` block comment: after `NOT` or `IN` in `a NOT IN (…)`, after `LIKE`, `GLOB` or `SIMILAR TO`, after `BETWEEN` or its `AND`, after `IS` or `NOT` in `a IS NOT NULL`, and after `ESCAPE`. A comment on the words of another operator, such as `@>`, goes after its right operand.

**Bad** (the comments are dropped)
```sql
SELECT
   a
FROM t
WHERE a NOT IN (1, 2)
  AND b BETWEEN 1 AND 10
  AND c IS NOT NULL
;
```

**Good**
```sql
SELECT
   a
FROM t
WHERE a NOT /* legacy codes */ IN (1, 2)
  AND b BETWEEN /* inclusive */ 1 AND 10
  AND c IS NOT /* set by the loader */ NULL
;
```

---

### Several comments on one expression — one per line

Nothing follows a `--` comment on its line, not even another comment. When several comments belong to one expression, the first stays after it and each of the others gets its own line.

**Bad**
```sql
SELECT
   a AS c -- first -- second
  ,b
FROM t
;
```

**Good**
```sql
SELECT
   a AS c -- first
  -- second
  ,b
FROM t
;
```

A comment on its own line above a column stays there, even when the column has a comment of its own, whatever the column starts with. The same goes for a `GROUP BY` or `ORDER BY` key and a `REPLACE` item.

**Bad** (the comment above moves into the column)
```sql
SELECT
   trim(name) /* as the customer entered it */ AS customer_name -- may be empty
  ,id
FROM customers
;
```

**Good**
```sql
SELECT
   -- as the customer entered it
   trim(name) AS customer_name -- may be empty
  ,id
FROM customers
;
```

---

### String literals — line breaks kept as written

A line break inside a string literal is part of its value. Jarify never re-indents the lines after it, wherever the literal is: in a column, a function argument, a `CASE` branch or a join condition.

**Bad** (each pass indents `two` further, changing the string)
```sql
SELECT
   'a' || if(x = 1, 'one
  two', 'b') AS v
FROM t
;
```

**Good**
```sql
SELECT
   'a' || if(x = 1, 'one
two', 'b') AS v
FROM t
;
```

A `SELECT` written on one line, such as a short scalar subquery in a `CASE` branch, has no alias alignment of its own: `(SELECT MAX(v) AS m FROM u)`, not `(SELECT MAX(v)      AS m FROM u)`.

---

### Block comments — lines kept as written

Jarify places a multi-line `/* … */` comment like any other comment but never re-indents the lines inside it: they stay exactly as written, so commented-out SQL keeps its layout and formatting the file again changes nothing.

**Bad** (each pass shifts the comment's lines two more columns)
```sql
,_managers AS
(
  SELECT
     m.user_id AS root_user_id
    ,u.active  AS user_active
  /* add in for testing
      ,u.manager_id AS direct_user_id
      */
  FROM _users m
)
```

**Good**
```sql
,_managers AS
(
  SELECT
     m.user_id AS root_user_id
    ,u.active  AS user_active
  /* add in for testing
    ,u.manager_id AS direct_user_id
    */
  FROM _users m
)
```

A block comment on a line of its own keeps a line of its own, as a `--` comment there does: between two `SELECT` columns it stays between them, above the first column or above a CTE it stays above it. One that fits on one line is written as a `--` comment.

**Bad** (the commented-out columns are pulled onto the line of `,b`)
```sql
SELECT
   a
  ,b /* ,c
  ,d */
  ,e
FROM t
;
```

**Good**
```sql
SELECT
   a
  ,b
  /* ,c
  ,d */
  ,e
FROM t
;
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

You can also set a minimum visible alias column with `min-column-alias`. Jarify then uses the greater of the configured minimum and the naturally computed alignment column. Longer expressions still win; the setting is a floor, not a fixed hard stop.

The floor is the same visible column in every context. `min-column-alias = N` pads expressions through column N, so `AS` starts in column N + 2 at the earliest. That holds whether the list is indented as the outer `SELECT`, a CTE body, a subquery, a macro body, a branch of a `UNION` or the `REPLACE` or `RENAME` list of a star.

Project config example:

```toml
[jarify]
min-column-alias = 24
```

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

**Also good** (`min-column-alias = 24`)
```sql
SELECT
   a                     AS one
  ,bb                    AS two
FROM t
;
```

#### Visual-guide interval

Set `alias_visual_guide_interval` (also accepted as `alias-visual-guide-interval`) to a positive integer `n` to put every aligned `AS` on an editor visual guide. The guide is the column `AS` starts in, counted from 1. Jarify takes the column where `AS` would otherwise start and moves it right to the first multiple of `n` at or after it. A column already on a guide stays where it is, and a longer expression moves `AS` to a later guide. Zero, a negative number or no value leaves the option unset, and output is unchanged.

DataGrip and the other JetBrains IDEs call these lines *Visual guides* (`Settings | Editor | Code Style | Visual guides`, or `ij_visual_guides` in EditorConfig). DataGrip takes an explicit comma-separated list of guide columns, such as `12,24,36`. Jarify deliberately takes one interval instead: `12` means guides at columns 12, 24, 36, 48 and so on.

The interval applies wherever jarify aligns column aliases:

- the query-wide column shared by the outer `SELECT` and its CTEs, nested CTEs included
- `SELECT` lists that align on their own, such as the branches of a top-level `UNION`
- multi-line expressions, which align by their closing line (`END AS …`)

A column whose last line is inside a string literal, such as `'line one<newline>line two' AS note`, aligns on its own with one space before `AS`, since the literal's lines are written as they are (see [String literals](#string-literals--line-breaks-kept-as-written)).
- the `REPLACE` and `RENAME` lists of a star

Table aliases in `FROM` and `JOIN` keep their own alignment.

When `min-column-alias` is also set, jarify applies the floor first and then moves to the next guide. `min-column-alias = 34` pads expressions through column 34, so `AS` starts in column 36 at the earliest. Adding `alias_visual_guide_interval = 12` puts `AS` in column 36, 48 or 60: the first of those that leaves at least one space after the longest expression in the query.

The interval is a personal editor preference, so it fits in your global config:

```toml
# ~/.config/jarify/config.toml
[jarify]
alias_visual_guide_interval = 12
```

**Before** (no interval: `customer_name` ends in column 16, so `AS` starts in column 18)
```sql
SELECT
   customer_name AS name
  ,id            AS customer_id
FROM customers
;
```

**After** (`alias_visual_guide_interval = 12`: `AS` moves to column 24)
```sql
SELECT
   customer_name       AS name
  ,id                  AS customer_id
FROM customers
;
```

**Also good** (`min-column-alias = 34` and `alias_visual_guide_interval = 12`: `AS` in column 36, or 48 when the longest expression needs it)
```sql
SELECT
   id                              AS order_id
  ,status                          AS order_status
FROM orders
;

SELECT
   id                                          AS order_id
  ,ifnull(shipping_address, billing_address)   AS address
FROM orders
;
```

---

### `JOIN` formatting — inline `ON`, aligned aliases

When a `FROM`/`JOIN` block contains only simple table references and/or `UNNEST` table-function calls, aliases are **right-aligned** — every alias ends at the same column, so the `ON` clauses line up too. That column is the first one that leaves at least one space between each table reference and its alias.

**Bad**
```sql
SELECT a FROM orders AS o LEFT JOIN users AS u ON u.id = o.user_id LEFT JOIN addresses AS addr ON addr.id = o.aid
```

**Good**
```sql
SELECT
   a
FROM orders            o
LEFT JOIN users        u ON u.id = o.user_id
LEFT JOIN addresses addr ON addr.id = o.aid
;
```

`UNNEST` table-function calls participate in the same alignment. Their alias name is aligned, and its column list follows it:

```sql
SELECT
   o.*
FROM offers                            o
CROSS JOIN UNNEST(o.group_by_values) gbv(group_by_value)
;
```

If any entry in the block is a subquery (multi-line), alignment is skipped for the entire block, but `ON` is still kept inline.

An `ON` condition that carries comments can't stay on one line, because a `--` comment would swallow the rest of it. It is laid out like `WHERE` instead: the first condition stays on the `JOIN` line, and each `AND` / `OR` goes on its own line, right-justified so the conditions line up after `ON`. A single commented condition stays inline. A comment written on its own line before the first condition goes above the `JOIN` line (see [Predicate comments](#predicate-comments--keep-or--and-outside-the-comment)).

```sql
SELECT
   x.a
  ,y.b
FROM some_table       x
LEFT JOIN other_table y ON x.id = y.id -- match
                        OR x.alt_id = y.id -- fallback
INNER JOIN third      z ON z.id = x.id
;
```

An `ON` condition holding a `CASE`, which is always multi-line, is laid out the same way, and the CASE is laid out under its keyword:

```sql
SELECT
   t.a
FROM t
INNER JOIN u ON u.k = CASE
                        WHEN t.x = 1
                        THEN 'one'
                        WHEN t.x = 2
                        THEN 'two'
                      END
            AND u.j = t.j
;
```

A comment on a `FROM` or `JOIN` table follows its alias, or the table when it has none, so the aliases stay aligned. When `ON` or `USING` follows it on the line, each comment is a `/* */` block comment.

**Bad** (the comment is dropped, or comes between the table and its alias)
```sql
FROM orders            o
LEFT JOIN users /* people */ u ON u.id = o.user_id
LEFT JOIN addresses addr ON addr.id = o.aid
CROSS JOIN regions
```

**Good**
```sql
FROM orders            o -- source
LEFT JOIN users        u /* people */ ON u.id = o.user_id
LEFT JOIN addresses addr ON addr.id = o.aid
CROSS JOIN regions -- every region
```

A nested join is written as a parenthesized group, which means the same as the form without parentheses. The group is laid out like a `FROM` clause: its first table on its own line, then one join per line, with aliases aligned.

**Bad** (written without parentheses, each `ON` far from its join)
```sql
SELECT tt.a FROM tbl tt LEFT JOIN users uu JOIN visits vv ON vv.uid = uu.id ON uu.id = tt.uid
```

**Good**
```sql
SELECT
   tt.a
FROM tbl tt
LEFT JOIN (
  users             uu
  INNER JOIN visits vv ON vv.uid = uu.id
) ON uu.id = tt.uid
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
INNER JOIN bar ON foo.id = bar.id
;
```

Set `normalize_join = false` to keep a bare `JOIN` as written.

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

Some projects want every outer join to say `OUTER`, so it stands apart from `INNER JOIN`, which they keep for joins that filter rows. Set `explicit-outer-join` to reverse the rule: `fmt` keeps `OUTER` on `LEFT` and `RIGHT` joins and adds it where it is missing. The same applies to `ASOF` and `NATURAL` joins (`ASOF LEFT OUTER JOIN`). `FULL` joins keep whichever form they were written in, and `INNER`, `CROSS`, `SEMI`, `ANTI` and `POSITIONAL` joins are unchanged. Table aliases stay aligned to the longer keyword.

Project config example:

```toml
[jarify]
explicit-outer-join = true
```

Like the other join keyword rules, this applies during `jarify fmt` only: `jarify lint` doesn't report a `LEFT JOIN`, so use `jarify fmt --check` to catch one.

**Bad** (with `explicit-outer-join = true`)
```sql
SELECT o.id, c.name, s.status FROM orders AS o JOIN customers AS c ON c.id = o.customer_id LEFT JOIN shipments AS s ON s.order_id = o.id
```

**Good** (with `explicit-outer-join = true`)
```sql
SELECT
   o.id
  ,c.name
  ,s.status
FROM orders               o
INNER JOIN customers      c ON c.id = o.customer_id
LEFT OUTER JOIN shipments s ON s.order_id = o.id
;
```

---

### `IS NOT NULL`, `IS NOT true` preserved

`IS NOT NULL`, `IS NOT true` and `IS NOT false` are kept as-is and never rewritten to `NOT x IS NULL` or `NOT x IS true`. A `NOT` written in front, as in `NOT x IS NULL`, moves after `IS`: DuckDB reads both forms the same way. A `NOT` in front of parentheses, as in `NOT (x IS true)`, stays where it is.

**Bad** (what some formatters emit)
```sql
WHERE NOT end_date IS NULL
  AND NOT is_active IS TRUE
```

**Good**
```sql
WHERE end_date IS NOT NULL
  AND is_active IS NOT true
```

---

### `NOT IN`, `NOT BETWEEN` — `NOT` after the operand

`NOT IN`, `NOT BETWEEN`, `NOT SIMILAR TO` and `NOT GLOB` keep `NOT` after the operand, as `NOT LIKE` and `IS NOT NULL` do. A `NOT` written in front of such a predicate, as in `NOT a IN (1, 2)`, moves after the operand too: DuckDB reads both forms as `NOT (a IN (1, 2))`. A `NOT` in front of parentheses, as in `NOT (a IN (1, 2))`, stays where it is.

**Bad**
```sql
WHERE NOT user_id IN (SELECT user_id FROM excluded_users)
  AND NOT created_on BETWEEN '2024-01-01' AND '2024-12-31'
```

**Good**
```sql
WHERE user_id NOT IN (SELECT user_id FROM excluded_users)
  AND created_on NOT BETWEEN '2024-01-01' AND '2024-12-31'
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

`::` binds tighter than every operator except `.`, so a cast of an operator expression keeps it in parentheses. Without them, `CAST(a + b AS int)` would become `a + b::int`, which casts only `b`.

**Bad**
```sql
SELECT CAST(a + b AS int) AS total, CAST(x IN (1, 2) AS int) AS is_small, CAST(-a AS text) AS label FROM t
```

**Good**
```sql
SELECT
   (a + b)::int       AS total
  ,(x IN (1, 2))::int AS is_small
  ,(-a)::text         AS label
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
FROM offers                   o
INNER JOIN fact_transactions ft ON o.id = ft.offer_id
;
```

---

### Lambdas — `lambda x: body`

DuckDB deprecated the arrow lambda (`x -> body`) in favour of `lambda x: body`. Jarify writes the lambda argument of DuckDB's list functions (`list_transform`, `list_filter`, `list_reduce` and their `array_` and short aliases) in the `lambda` form, also in method-call syntax (`names.list_filter(lambda x: …)`), and the lambda in `COLUMNS(lambda c: …)`. It spells `LAMBDA x : body` the same way. Several parameters take no parentheses.

Any other arrow is left as written, because DuckDB reads it as JSON extraction: `doc -> 'key'` in an `ifnull()`, in a list function's first argument, or in a call to a user-defined macro.

**Bad**
```sql
SELECT list_transform(tags, t -> upper(t)) AS tags, list_reduce(amounts, (acc, x) -> acc + x) AS total, ifnull(doc -> 'label', 'none') AS label FROM t
```

**Good**
```sql
SELECT
   list_transform(tags, lambda t: upper(t))     AS tags
  ,list_reduce(amounts, lambda acc, x: acc + x) AS total
  ,ifnull(doc -> 'label', 'none')               AS label
FROM t
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

When `list(DISTINCT expr ...)` wraps across lines, `DISTINCT` appears on its own line.

**Bad**
```sql
SELECT ARRAY_AGG(DISTINCT (active_ingredient_key, quantity, uom_key)::active_ingredient_struct) FROM t
```

**Good**
```sql
SELECT
   list(
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

### `ORDER BY` inside aggregates — own line when wrapping

An aggregate with an `ORDER BY` stays on one line while the whole call fits, as in `list(a ORDER BY b)` or `STRING_AGG(a, ', ' ORDER BY b)`. When it doesn't, the call wraps: its arguments go one per line, like any wrapped call's, and `ORDER BY` goes on its own line below them, lined up with them. A key list that still doesn't fit puts one key per line, as in a window spec. `STRING_AGG`'s separator and the other arguments of an aggregate such as `arg_max` count as arguments. A `CASE` never fits on a line: an argument holding one puts `ORDER BY` on its own line, and a key list holding one puts one key per line.

**Bad**
```sql
SELECT
   list({'nomination_id': nomination_id, 'created_at': created_at, 'created_on': created_at::date} ORDER BY created_at DESC, nomination_id DESC) AS noms
  ,list(nomination_id ORDER BY created_at DESC, nomination_id DESC, client_id, program_id, nomination_application_id, employee_user_id, reporting_period_key) AS ids
  ,STRING_AGG(nomination_application_name, ', ' ORDER BY nomination_application_name, nomination_application_id DESC, created_at DESC) AS names
FROM t
GROUP BY ALL
```

**Good**
```sql
SELECT
   list(
     {'nomination_id': nomination_id, 'created_at': created_at, 'created_on': created_at::date}
     ORDER BY created_at DESC, nomination_id DESC
  ) AS noms
  ,list(
     nomination_id
     ORDER BY
        created_at DESC
       ,nomination_id DESC
       ,client_id
       ,program_id
       ,nomination_application_id
       ,employee_user_id
       ,reporting_period_key
  ) AS ids
  ,STRING_AGG(
     nomination_application_name
    ,', '
     ORDER BY nomination_application_name, nomination_application_id DESC, created_at DESC
  ) AS names
FROM t
GROUP BY ALL
;
```

---

### Comments inside one-line constructs — wrap, or use `/* */`

Window specs, function calls, `IN (…)` lists and list literals stay on one line when they fit. A `--` comment inside one would comment out the rest of that line, so a construct that carries a comment takes its multi-line form instead, and each `--` comment ends its line:

- A window spec puts `PARTITION BY`, `ORDER BY` and the frame on their own lines, one key per line in leading-comma style, and the closing `)` lines up under the function name. A comment on `ORDER BY` itself stays on its own line above it.
- A function call, `IN (…)` list, list literal or struct literal puts one argument per line, like any wrapped call. An aggregate's `ORDER BY` stays with its argument on that argument's line. A comment written after the opening `(`, `[` or `{` goes after the first argument, or after the call when it has none, as in `ROW_NUMBER()`; one on a struct entry's `:` goes after its value. A comment on its own line above a list or struct literal stays above it.

**Bad** (the `)` and alias are commented out)
```sql
SELECT
   ROW_NUMBER() OVER (PARTITION BY userId, customFieldId ORDER BY id DESC -- latest first) AS rev_seq
FROM t
```

**Good**
```sql
SELECT
   ROW_NUMBER() OVER (
     PARTITION BY
        userId
       ,customFieldId
     ORDER BY
        id DESC -- latest first
   ) AS rev_seq
  ,list(
     a ORDER BY b -- oldest first
  ) AS a_list
FROM t
;
```

A struct literal keeps each entry's comments with it, including entries commented out on their own lines:

**Bad** (the comments are dropped)
```sql
SELECT
   {'attribute': attribute, 'seq': seq, 'value': mapped_value} AS custom_field
FROM t
;
```

**Good**
```sql
SELECT
   {
     'attribute': attribute -- the field's name
    ,'seq': seq
    -- ,'provided_value': provided_value
    ,'value': mapped_value
  } AS custom_field
FROM t
;
```

A comment in an aggregate's `FILTER (WHERE …)`, written on `FILTER`, its `(` or `WHERE`, goes after `WHERE`. One written before `OVER`, on `OVER` or after its `(` goes after the whole call, as one after the call itself does. One on `DISTINCT ON` stays after `ON`. The ones that SQL follows on their line are written as `/* */` block comments.

**Good**
```sql
SELECT DISTINCT ON /* the latest row per user */ (user_id)
   user_id
  ,COUNT(*) FILTER(WHERE /* paid only */ amount > 0) OVER (PARTITION BY user_id) AS paid_orders -- per user
FROM t
;
```

A comment that has no line end to sit at, such as one inside an arithmetic expression, a lambda's body or a `USING (…)` list, or before an alias, a `::` cast or `DESC`, is written as a `/* */` block comment:

```sql
SELECT
   a /* note */ + 1 AS c
  ,b /* raw */::int AS d
FROM t
;
```

A cast value that needs parentheses and carries a comment puts its parentheses on lines of their own, as a commented parenthesized expression does:

```sql
SELECT
   (
    a /* note */ + b
  )::int AS c
  ,d
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
   END         AS abc
FROM data
;
```

A `WHEN` condition that wraps, such as an `IN (…)` list, an `IN (subquery)` or parentheses, is laid out as after `WHERE`: a list's values start three columns past `WHEN`, and its `)` goes under `WHEN`. After an `AND` or `OR`, they go under the connector, as in `WHERE`.

**Bad** (the `)` one column right of `WHEN`)
```sql
SELECT
   CASE
     WHEN status IN (
         'cancelled_by_customer'
        ,'cancelled_by_merchant'
        ,'refunded_in_full'
        ,'refunded_in_part'
        ,'charged_back'
        ,'disputed'
      )
     THEN 'reversed'
     WHEN status = 'shipped'
     THEN 'done'
   END AS outcome
FROM orders
;
```

**Good**
```sql
SELECT
   CASE
     WHEN status IN (
        'cancelled_by_customer'
       ,'cancelled_by_merchant'
       ,'refunded_in_full'
       ,'refunded_in_part'
       ,'charged_back'
       ,'disputed'
     )
     THEN 'reversed'
     WHEN status = 'shipped'
     THEN 'done'
   END AS outcome
FROM orders
;
```

A CASE is laid out the same way wherever it appears, relative to the column its `CASE` keyword starts in: in a searched CASE, `WHEN`, `THEN` and `ELSE` start two columns past the `C` of `CASE` and `END` sits under it; in a simple CASE, `WHEN` and `ELSE` start one column past the `C` and `END` one column before it (under the comma, in a SELECT list). That holds for a CASE in another CASE's branch, after an operator, in parentheses, and in a `WHERE`, `HAVING`, `QUALIFY` or `JOIN … ON` condition. With trailing commas there's no comma for a simple CASE's `END` to sit under, so it sits under the `C`, as in a searched CASE.

**Bad** (a CASE left on one line, or its lines not under its `CASE`)
```sql
SELECT
   CASE
     WHEN y = 1
     THEN CASE WHEN x = 1 THEN 'one' WHEN x = 2 THEN 'two' ELSE 'many' END
     WHEN y = 2
     THEN 'b'
   END AS nested
  ,(CASE WHEN x = 1 THEN 'one' WHEN x = 2 THEN 'two' ELSE 'many' END)::text AS cast_text
  ,b || CASE k
    WHEN 1 THEN 'one'
    WHEN 2 THEN 'two'
  END AS suffixed
FROM t
WHERE CASE
   WHEN x = 1
   THEN 'one'
   WHEN x = 2
   THEN 'two'
   ELSE 'many'
 END = 'one'
  AND c = 3
```

**Good**
```sql
SELECT
   CASE
     WHEN y = 1
     THEN CASE
            WHEN x = 1
            THEN 'one'
            WHEN x = 2
            THEN 'two'
            ELSE 'many'
          END
     WHEN y = 2
     THEN 'b'
   END         AS nested
  ,(CASE
      WHEN x = 1
      THEN 'one'
      WHEN x = 2
      THEN 'two'
      ELSE 'many'
    END)::text AS cast_text
  ,b || CASE k
         WHEN 1 THEN 'one'
         WHEN 2 THEN 'two'
       END     AS suffixed
FROM t
WHERE CASE
        WHEN x = 1
        THEN 'one'
        WHEN x = 2
        THEN 'two'
        ELSE 'many'
      END = 'one'
  AND c = 3
;
```

A construct that stays on one line when it fits doesn't when it holds a CASE, since the CASE never fits on one line. A `JOIN … ON` condition holding one is laid out like `WHERE` (see [`JOIN` formatting](#join-formatting--inline-on-aligned-aliases)); a subquery holding one takes its multi-line form; an `IN (…)` list or list literal puts one value per line; a window spec puts each clause on its own line, and a `PARTITION BY` or `ORDER BY` holding the CASE one key per line (see [Window specs](#window-specs--one-clause-per-line-when-wrapping)); and an aggregate's `ORDER BY` goes on its own line under the argument (see [`ORDER BY` inside aggregates](#order-by-inside-aggregates--own-line-when-wrapping)).

A CASE passed as a function argument, `string_agg()` included, is laid out as in a SELECT list. The call puts each argument on its own line, even when the call would fit on one, so the CASE starts its line, as in a SELECT list.

**Bad**
```sql
SELECT
   if(x, CASE WHEN a THEN 1 WHEN b THEN 2 ELSE 3 END, 0) AS k
  ,format('{}: {}', y, CASE z WHEN 1 THEN 'one' ELSE 'other' END) AS m
FROM t
```

**Good**
```sql
SELECT
   if(
      x
     ,CASE
        WHEN a
        THEN 1
        WHEN b
        THEN 2
        ELSE 3
      END
     ,0
  ) AS k
  ,format(
     '{}: {}'
    ,y
    ,CASE z
      WHEN 1 THEN 'one'
      ELSE 'other'
    END
  ) AS m
FROM t
;
```

A comment on `WHEN`, `THEN` or `ELSE`, written above the keyword or after it, goes on its own line above the line the keyword starts, as a comment on `AND` / `OR` goes above the connector. In a simple CASE, where `THEN` shares the `WHEN` line, it goes above the `WHEN` line. A single-branch CASE with such a comment stays a CASE instead of becoming `if()`.

**Bad** (the comments are dropped)
```sql
SELECT
   CASE
     WHEN country = 'SER'
     THEN 'SRB'
     WHEN country = 'ROM'
     THEN 'ROU'
     ELSE country
   END AS iso_code
FROM t
;
```

**Good**
```sql
SELECT
   CASE
     -- legacy codes
     WHEN country = 'SER'
     THEN 'SRB'
     WHEN country = 'ROM'
     -- renamed in 2002
     THEN 'ROU'
     -- already ISO
     ELSE country
   END AS iso_code
FROM t
;
```

---

### `SELECT *` — rewritten as FROM-first

Plain, unmodified `SELECT *` is rewritten to DuckDB's FROM-first syntax, omitting the `SELECT` clause entirely. Applies only when there are no JOINs. A query already written FROM-first keeps that form with its joins, one per line like any other join, while `SELECT * FROM t JOIN u` keeps its `SELECT`:

```sql
FROM rpt.points_with_monetary_value p
SEMI JOIN common.dates              d ON d.the_date = p.the_date
SEMI JOIN _clients                  c USING (parent_client_id)
;
```

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

A comment above a FROM-first query stays above it, as it does above a `SELECT` query. After a `WITH` clause it stays between the last CTE and the query. A FROM-first query with a select list, such as `FROM orders SELECT id`, is written `SELECT`-first, and the comment above it still goes above the whole query.

**Bad** (the comment is deleted)
```sql
FROM orders
;
```

**Good**
```sql
-- every order, including cancelled ones
FROM orders
;
```

Modified stars stay in `SELECT` form and expand their modifiers. `REPLACE` and `RENAME` keep jarify's alias alignment inside the modifier list.

**Bad**
```sql
SELECT * RENAME (id AS vendor_id, name AS vendor_name) FROM orders
```

**Good**
```sql
SELECT
   *
   RENAME (
      id   AS vendor_id
     ,name AS vendor_name
   )
FROM orders
;
```

---

### Statement terminator

Every statement ends with a semicolon on its own line, followed by a blank line. SQLMesh macro statements, described next, are the exception.

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

Comments after the last statement, such as a commented-out test query, are kept exactly as written after its `;`: the same lines and blank lines, with no `;` added after them. A comment on the same line as the last statement's final token stays on that line.

**Bad**
```sql
SELECT
   a
FROM t
;

-- one -- two /*
SELECT b
FROM u
*/
;
```

**Good**
```sql
SELECT
   a
FROM t
;

-- one

-- two

/*
SELECT b
FROM u
*/
```

---

### SQLMesh macro statements — kept as written

In a SQLMesh model, Jarify keeps the `MODEL (...)` block as written. It does the same for each top-level statement that is only a macro call followed by `;`: `@DEF(...)` definitions and pre- or post-statements such as `@ensure_sql_macro(...)`. The statement keeps its own line and its `;`, and the comments above it and the blank lines around it are kept too. The model's query and other SQL statements are formatted as usual, including macros used inside them, such as `FROM @read_parquet(...)`.

A macro statement that shares a line with other SQL is formatted like any other statement.

**Bad**
```sql
MODEL (
  name sales.orders,
);

-- Where the source files live.
@DEF(source_db, 'X');
@DEF(source_schema, 'dbo');

select id, amount from @read_parquet(@source_db, @source_schema, 'orders')
```

**Good**
```sql
MODEL (
  name sales.orders,
);

-- Where the source files live.
@DEF(source_db, 'X');
@DEF(source_schema, 'dbo');

SELECT
   id
  ,amount
FROM @read_parquet(@source_db, @source_schema, 'orders')
;
```

---

### `CREATE TABLE` layout

The opening parenthesis goes on its own line. Column names are padded to align all type tokens, and types are padded to align all constraint tokens when any column carries constraints. A blank line separates column definitions from table-level constraints (`PRIMARY KEY`, `UNIQUE`, `CHECK`, etc.). A comment after a column definition stays after it, as in a `SELECT` list.

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

A row keeps its comments, as a `SELECT` list's column does: one after the row stays after it, and one on its own line between two rows stays on its own line above the next row. A comment on `VALUES` goes at the end of the `VALUES` line.

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

**Good** (with comments)
```sql
WITH _overrides (country_code, currency_code) AS
(
  VALUES -- currencies the source gets wrong
     ('MDG', 'MGA') -- madagascar
    -- added in 2024
    ,('ZWE', 'ZWG')
)
SELECT
   country_code
  ,currency_code
FROM _overrides
;
```

---

## Lint Rules

Rules in this section may lint only, auto-fix during `fmt`, or do both. All rules default to `warn`. Severity can be set to `off`, `warn`, or `error` in `jarify.toml`.

### Comment overrides

Use `jarify` comment directives when one line or region needs an exception without changing repo-wide config.

Supported directives:

- `-- jarify: disable-line <rule>` — disable a rule on the current line
- `-- jarify: disable-next-line <rule>` — disable a rule for the entire next SQL statement, including multi-line statements
- `-- jarify: disable <rule>` / `-- jarify: enable <rule>` — disable a rule for a region
- `-- jarify: disable-file <rule>` — disable a rule for the whole file
- `-- jarify: set max_line_length = 140` / `-- jarify: reset max_line_length` — override line length for following statements until reset
- `-- jarify: set min-column-alias = 80` / `-- jarify: reset min-column-alias` — set or clear a minimum visible column-alias alignment floor for following statements
- `-- jarify: set alias-visual-guide-interval = 12` / `-- jarify: reset alias-visual-guide-interval` — set or clear the visual-guide interval for column-alias alignment for following statements
- `-- jarify: set <option> = true` / `false`, e.g. `-- jarify: set prefer-from-first = false` / `-- jarify: reset prefer-from-first` — turn an on/off option such as `explicit-outer-join` or `normalize-join` on or off for following statements

A `set` lasts until the next `set` or `reset` of the same option. A `set` that names an unknown option, or gives a value the option can't take, is ignored.

Rules use their lint names such as `no-select-star`, `cte-naming`, or `prefer-if-over-case`. The wildcard `all` matches every rule — handy for silencing files edited in a non-DuckDB IDE. `enable all` closes every open `disable` region.

**Example**
```sql
-- jarify: disable-next-line prefer-if-over-case
SELECT CASE WHEN is_large THEN 'big' ELSE 'small' END FROM sizes
```

**File-specific alias floor**
```sql
-- jarify: set min-column-alias = 80
SELECT short_col AS short_alias, other_col AS other_alias FROM t
;

-- jarify: reset min-column-alias
```

**Disable everything for a file**
```sql
-- jarify: disable-file all
SELECT * FROM scratchpad
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

When `prefer_from_first = true` (the default), only plain single-table `SELECT *` queries are exempt because the formatter rewrites them to FROM-first syntax (`FROM t`). Modified stars such as `SELECT * EXCLUDE (...)` and `SELECT * REPLACE (...)` are still flagged, as are `SELECT *` queries with JOINs.

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
| `varchar` | `text` |

**Bad**
```sql
CREATE TABLE t (score FLOAT, short_label VARCHAR)
```

**Good**
```sql
CREATE TABLE t (score real, short_label text)
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

**Auto-fixed by `fmt`.** Rewrites explicit `GROUP BY col1, col2, ...` to `GROUP BY ALL` when every standalone non-aggregate `SELECT` expression is listed. Mixed aggregate/non-aggregate expressions stay explicit because DuckDB can reject `GROUP BY ALL` for that shape. A list that carries a comment stays explicit too, and isn't flagged: `GROUP BY ALL` would delete the comment, even one with the same text as a comment in the `SELECT` list.

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

Applies only to *searched* CASE with exactly one WHEN branch. Multi-branch CASE and simple CASE (`CASE expr WHEN lit …`) are left unchanged. A CASE with a comment inside its WHEN, THEN or ELSE expression is also left unchanged, so the comment stays beside the branch it documents; the rule only rewrites a CASE that carries no comment. So is a CASE with a comment attached to the CASE itself, such as one written on the line above a CASE nested in another CASE's ELSE, because an `if()` call can't keep a comment of its own. A comment written above a CASE that makes up a whole column, `GROUP BY` key or `ORDER BY` key belongs to the column, though, so that CASE is still rewritten, and the comment stays above the column. When the original `CASE` has no `ELSE`, jarify emits an explicit `NULL` third argument because DuckDB's `IF()` requires three arguments.

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

A CASE nested in another one is rewritten in the same pass, whether it sits in the THEN or ELSE of a CASE that becomes `if()` or in a branch of a multi-branch CASE that stays a CASE:

**Bad**
```sql
SELECT
   CASE WHEN a > 1 THEN 'big' ELSE CASE WHEN b IS NULL THEN 'none' ELSE 'small' END END AS size
FROM t
```

**Good**
```sql
SELECT
   if(a > 1, 'big', if(b IS NULL, 'none', 'small')) AS size
FROM t
;
```

When a compact `if(cond, then, else)` call exceeds `max_line_length`, expand the outer
`if()` call across multiple lines. Keep the condition compact on one line, but let an
overlong `true` or `false` branch use its normal nested wrapping. An `if()` whose
arguments contain a comment is always expanded, and each commented argument keeps its
normal multi-line rendering, so the comment ends its line. An `if()` whose arguments
contain a `CASE` is always expanded too, and that argument keeps its multi-line layout
(see [`CASE` — always multi-line](#case--always-multi-line)).

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
