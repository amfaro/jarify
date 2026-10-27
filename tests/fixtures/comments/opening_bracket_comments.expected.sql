-- A comment after an opening bracket goes on the first item
SELECT
   coalesce(
     a -- first non-null
    ,b
    ,c
  )                 AS v
  ,a /* raw */::int AS w
  ,COUNT(
     * -- all rows
  )                 AS n
  ,[
     1 -- first
    ,2
  ]                 AS l
FROM t
WHERE a IN (
   1 -- small ones
  ,2
)
;

SELECT
   a
FROM t
INNER JOIN u USING (id /* the key */)
;

-- A comment after a parenthesis that groups a condition follows the group
SELECT
   a
FROM t
WHERE x = 1
  AND (a = 1 OR b = 2) -- either one
;
