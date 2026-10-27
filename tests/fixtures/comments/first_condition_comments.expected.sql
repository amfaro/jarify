-- WHERE, one condition: the comment goes above WHERE
SELECT
   a
FROM t
-- only active rows
WHERE a = 1
;

-- WHERE, several conditions
SELECT
   a
FROM t
-- only active rows
WHERE a = 1
  AND b = 2
  AND c IS NOT NULL
;

-- WHERE with OR at the top level
SELECT
   a
FROM t
-- either flag
WHERE a = 1 OR b = 2
;

-- HAVING, one condition
SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
-- big groups
HAVING COUNT(*) > 1
;

-- HAVING, several conditions
SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
-- big groups
HAVING COUNT(*) > 1
   AND a IS NOT NULL
    OR a = 0
;

-- QUALIFY keeps its condition on the next line, so the comment stays there
SELECT
   a
FROM t
QUALIFY
  -- latest row per a
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC) = 1 AND a > 2
;

-- JOIN ... ON: the comment goes above the JOIN
SELECT
   x.a
  ,y.b
FROM some_table       x
-- match on id
LEFT JOIN other_table y ON y.id = x.id AND y.k IS NOT NULL
INNER JOIN third      z ON z.id = x.id
;
