-- array_agg() is an alias; jarify normalizes to list()
SELECT array_agg(x) FROM t;
SELECT array_agg(x ORDER BY y) FROM t;
SELECT array_agg(DISTINCT x) FROM t GROUP BY z;
-- list() passthrough — no change
SELECT list(x) FROM t;
SELECT list(x ORDER BY y) FROM t;
