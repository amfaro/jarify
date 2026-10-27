-- A commented argument wraps the call one argument per line
SELECT
   foo(
     a -- first
    ,b
  ) AS c1
  ,bar(
     a
    ,b -- last
  ) AS c2
  ,ifnull(
     a
    ,nullif(
       b -- inner
      ,''
    )
  ) AS c3
FROM t
;

-- Aggregate ORDER BY comments
SELECT
   list(
     a ORDER BY b -- oldest first
  ) AS c1
  ,list(
     a ORDER BY b DESC -- newest first
  ) AS c2
  ,STRING_AGG(
     a
    ,',' ORDER BY b -- alphabetical
  ) AS c3
FROM t
GROUP BY ALL
;

-- IN lists and list literals
SELECT
   a
FROM t
WHERE a IN (
   1 -- one
  ,2 -- two
)
;

SELECT
   [
     1 -- one
    ,2
  ] AS l
;

-- A call without comments stays inline
SELECT
   foo(a, b)          AS c
  ,list(a ORDER BY b) AS d
FROM t
GROUP BY ALL
;
