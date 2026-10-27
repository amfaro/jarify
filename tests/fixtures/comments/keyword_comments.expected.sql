-- A comment after NOT stays after it
SELECT
   a
FROM t
WHERE NOT /* negated */ a
;

SELECT
   a
FROM t
WHERE b = 1
  AND NOT /* neither branch */ (c = 1 OR d = 2)
;

SELECT
   a
FROM t
-- above not
WHERE NOT a
;

-- NOT IN puts NOT after the operand, so the comment goes at the end
SELECT
   a
FROM t
WHERE a NOT IN (1, 2) -- not listed
  AND b = 1
;

-- Comments on QUALIFY go above it, as for WHERE and HAVING
SELECT
   a
FROM t
-- latest
QUALIFY
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC) = 1
;

SELECT
   a
FROM t
-- one per a
-- latest first
QUALIFY
  ROW_NUMBER() OVER (PARTITION BY a ORDER BY b DESC) = 1
;

-- Comments on ON or USING go above the join, as for WHERE
SELECT
   t.a
  ,u.b
  ,v.c
FROM t
-- same id
INNER JOIN u ON u.id = t.id
-- optional
LEFT JOIN v ON v.id = t.id AND v.k = 1
-- by id
LEFT JOIN w USING (id)
;

-- Comments on UNION ALL go above it
SELECT
   a
FROM t
-- the managers too
UNION ALL
SELECT
   b
FROM u
;
