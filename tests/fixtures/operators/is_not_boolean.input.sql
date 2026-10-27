-- IS NOT TRUE and IS NOT FALSE keep NOT after IS, as IS NOT NULL does
SELECT a FROM t WHERE a IS NOT TRUE AND b IS NOT FALSE AND c IS NOT NULL
;

-- A NOT written in front moves after IS too; parentheses keep it in front
SELECT
  NOT a IS TRUE AS x,
  NOT (b IS FALSE) AS y,
  c IS TRUE AS z
FROM t
;
