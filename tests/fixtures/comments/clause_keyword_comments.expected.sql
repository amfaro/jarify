-- Comments on WINDOW go above it, like those on QUALIFY
SELECT
   SUM(a) OVER w AS s
FROM t
-- by a
WINDOW w AS (ORDER BY a)
;

SELECT
   SUM(a) OVER w AS s
FROM t
-- by a
WINDOW w AS (ORDER BY a) -- ascending
;

-- Comments on DISTINCT ON stay after ON
SELECT DISTINCT ON /* one per a */ (a)
   a
  ,b
FROM t
;

SELECT DISTINCT ON /* one per a */ (a)
   a
  ,b
FROM t
;

-- Comments in FILTER (WHERE …) go after WHERE; those before OVER, after the window
SELECT
   COUNT(*) FILTER (WHERE /* active */ active)     AS n
  ,COUNT(*) FILTER (WHERE /* recent */ d > 1)      AS m
  ,COUNT(*) FILTER (WHERE a) OVER (PARTITION BY b) AS o -- per b
  ,COUNT(*) OVER (PARTITION BY c)                  AS p -- per c
FROM t
;
