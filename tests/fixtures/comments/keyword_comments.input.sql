-- A comment after NOT stays after it
SELECT a FROM t WHERE NOT /* negated */ a
;

SELECT a FROM t
WHERE b = 1
  AND NOT -- neither branch
  (c = 1 OR d = 2)
;

SELECT a FROM t
WHERE
  -- above not
  NOT a
;

-- NOT IN puts NOT after the operand, so the comment goes at the end
SELECT a FROM t WHERE NOT /* not listed */ a IN (1, 2) AND b = 1
;

-- Comments on QUALIFY go above it, as for WHERE and HAVING
SELECT a FROM t QUALIFY /* latest */ row_number() OVER (PARTITION BY a ORDER BY b DESC) = 1
;

SELECT a FROM t
-- one per a
QUALIFY -- latest first
  row_number() OVER (PARTITION BY a ORDER BY b DESC) = 1
;

-- Comments on ON or USING go above the join, as for WHERE
SELECT t.a, u.b, v.c
FROM t
INNER JOIN u ON /* same id */ u.id = t.id
LEFT JOIN v ON -- optional
  v.id = t.id
  AND v.k = 1
LEFT JOIN w
  -- by id
  USING (id)
;

-- Comments on UNION ALL go above it
SELECT a FROM t
UNION ALL -- the managers too
SELECT b FROM u
;
