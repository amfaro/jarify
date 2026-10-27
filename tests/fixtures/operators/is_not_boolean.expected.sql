-- IS NOT TRUE and IS NOT FALSE keep NOT after IS, as IS NOT NULL does
SELECT
   a
FROM t
WHERE a IS NOT true
  AND b IS NOT false
  AND c IS NOT NULL
;

-- A NOT written in front moves after IS too; parentheses keep it in front
SELECT
   a IS NOT true    AS x
  ,NOT (b IS false) AS y
  ,c IS true        AS z
FROM t
;
