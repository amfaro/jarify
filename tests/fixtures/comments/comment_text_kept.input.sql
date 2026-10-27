-- Comment and string text is kept as written, even IFNULL, NUMERIC and ::filter
SELECT
  IFNULL(a, 0) AS v, -- IFNULL(a, 0) on purpose
  b::NUMERIC AS n, /* NUMERIC, not decimal */
  'IFNULL(a, 0)' AS s,
  '::filter[]' AS f,
  []::filter[] AS e
FROM t
;
