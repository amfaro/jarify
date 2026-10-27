-- A comment between two columns stays between them, after a column ending in ")" too
SELECT
   ifnull(a, 1)
  -- between ifnull and y
  ,x AS y
  ,f(b)
  -- between f and d
  ,d
  ,(c + 1)
  -- between the parenthesis and e
  ,e
FROM t
;

-- So does one in a GROUP BY, an ORDER BY, an IN list and a list literal
SELECT
   lower(a) AS a
  ,[f(a)
  -- between the items
  ,b] AS l
FROM t
WHERE c IN (
   g(a)
  -- between the values
  ,2
)
GROUP BY
   lower(a)
  -- between the keys
  ,l
ORDER BY
   lower(a)
  -- between the keys
  ,l
;

-- A comment above a column stays above it, whatever the column starts with
SELECT
  -- above the negation
  -a AS v
  -- above the method call
  ,x.title_case() AS w
  -- above the qualified method call
  ,t.x.upper() AS u
  -- above the bitwise not
  ,~b AS n
  -- above the interval
  ,INTERVAL 1 DAY AS i
  -- above the typed literal
  ,DATE '2020-01-01' AS d
FROM t
;

-- A comment above a CASE and one after it both stay, through the rewrite to if()
SELECT
  -- above the case
  CASE WHEN a THEN 1 ELSE 0 END -- after the case
  ,b
FROM t
;

-- The comments on an unaliased operator column are written once
SELECT
   a
  -- before the plus
  + 1
  ,b * -- after the times
   2
  ,c - 1
  -- after the minus column
  ,d
FROM t
;
