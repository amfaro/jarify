-- A commented subquery or IF() argument can't stay on one line, so it takes the expanded form
SELECT a FROM t
WHERE x IN (SELECT y FROM u WHERE y IS NOT NULL -- keep
            OR z = 1)
;

SELECT a FROM (SELECT a FROM u WHERE a IS NOT NULL -- keep
  AND b = 1) s
;

SELECT if(a IS NOT NULL -- has a
  OR b > 1, 1, 2) AS x
FROM t
;
