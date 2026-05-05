-- array_agg() is an alias; jarify normalizes to list()
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

-- list() passthrough — no change
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
