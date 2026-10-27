-- A comment on a word of an operator stays after that word
SELECT a FROM t
WHERE a NOT /* not */ IN (1, 2)
  AND b NOT IN /* in */ (1, 2)
  AND c NOT -- not like
  LIKE 'x%'
  AND d LIKE /* like */ 'y%'
  AND e NOT /* not */ BETWEEN 1 AND 2
  AND f BETWEEN -- from
  1 AND -- to
  2
;

-- IS, IS NOT and IS DISTINCT FROM
SELECT a FROM t
WHERE a IS /* is */ NOT NULL
  AND b IS NOT -- not
  NULL
  AND c IS /* is */ NULL
  AND d IS NOT /* not */ TRUE
  AND e IS /* is */ DISTINCT FROM f
;

-- In a SELECT list, a subquery IN and with ESCAPE
SELECT
  a NOT /* not */ IN (1, 2) AS x,
  b IN /* in */ (SELECT b FROM u) AS y,
  c NOT LIKE 'x!%' ESCAPE /* escape */ '!' AS z
FROM t
;

-- Other operators keep the comment after their right operand
SELECT a FROM t WHERE l @> /* contains */ [1, 2]
;
