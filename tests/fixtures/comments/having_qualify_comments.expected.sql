SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
HAVING COUNT(*) > 1 -- first
    OR a IS NOT NULL -- second
;

SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
HAVING COUNT(*) > 1
   -- own line
   AND a IS NOT NULL
;

SELECT
   a
FROM t
QUALIFY
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b) = 1 -- latest
  AND a IS NOT NULL -- present
;

SELECT
   a
FROM t
QUALIFY
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b) = 1
  -- own line
  AND a > 2
;
