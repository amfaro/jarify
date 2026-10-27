-- A comment on its own line above a column stays there when the column
-- has a comment of its own
SELECT
  -- above
  a AS v -- after
 ,b
FROM t
;

-- A block comment too, and in a CTE body; it doesn't move the AS
WITH c AS (
  SELECT
    /* above */
    a AS v -- after
   ,bbbbbbbb AS w
  FROM t
)
SELECT v, w FROM c
;

-- Above a later column, it lines up with the commas, where it stays on the
-- next pass
SELECT
  x,
  -- above
  a AS v, -- after
  /* above w */
  b AS w -- after w
FROM t
;

-- Whatever the column starts with
SELECT
  -- above a sum
  a + 1 AS v -- after
 ,b
FROM t
;

SELECT
  -- above a CASE
  CASE WHEN a THEN 1 WHEN b THEN 2 END AS v -- after
 ,c AS w
FROM t
;

-- A single-branch CASE still becomes if(), since the comment is the column's
SELECT
  x,
  -- above a CASE
  CASE WHEN a THEN 1 ELSE 0 END AS v -- after
FROM t
;

SELECT
  -- above a cast
  a::int AS v -- after
FROM t
;

-- These were lost
SELECT
  -- above parentheses
  (a + 1) * 2 AS v
 ,b
FROM t
;

SELECT
  -- above ifnull
  coalesce(a, 0) AS v -- after
FROM t
;

-- A column without an alias, a GROUP BY or ORDER BY key, a REPLACE item
SELECT
  -- above a column
  a + 1 -- after
 ,b
 ,count(*) AS n
FROM t
GROUP BY
  -- above a key
  a + 1 -- after the key
 ,b
ORDER BY
  -- above an order key
  b DESC -- after the order key
;

SELECT * REPLACE (
  -- above
  a + 1 AS a -- after
)
FROM t
;
