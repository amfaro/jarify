-- Comments on WINDOW go above it, like those on QUALIFY
SELECT SUM(a) OVER w AS s FROM t WINDOW /* by a */ w AS (ORDER BY a)
;

SELECT SUM(a) OVER w AS s FROM t
-- by a
WINDOW w AS -- ascending
  (ORDER BY a)
;

-- Comments on DISTINCT ON stay after ON
SELECT DISTINCT ON /* one per a */ (a) a, b FROM t
;

SELECT DISTINCT -- one per a
  ON (a) a, b FROM t
;

-- Comments in FILTER (WHERE …) go after WHERE; those before OVER, after the window
SELECT
  COUNT(*) FILTER /* active */ (WHERE active) AS n,
  COUNT(*) FILTER (WHERE -- recent
    d > 1) AS m,
  COUNT(*) FILTER (WHERE a) /* per b */ OVER (PARTITION BY b) AS o,
  COUNT(*) OVER -- per c
    (PARTITION BY c) AS p
FROM t
;
