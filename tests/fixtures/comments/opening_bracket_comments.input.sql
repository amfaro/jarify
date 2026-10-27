-- A comment after an opening bracket goes on the first item
SELECT
  coalesce( -- first non-null
    a, b, c) AS v,
  CAST( /* raw */ a AS int) AS w,
  COUNT( -- all rows
    *) AS n,
  [ -- first
    1, 2] AS l
FROM t
WHERE a IN ( -- small ones
  1, 2)
;

SELECT a
FROM t
INNER JOIN u USING ( -- the key
  id)
;

-- A comment after a parenthesis that groups a condition follows the group
SELECT a FROM t WHERE x = 1 AND ( -- either one
  a = 1 OR b = 2)
;
