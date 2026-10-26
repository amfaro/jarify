-- Own-line comments before OR branches
SELECT
   a
FROM t
WHERE a IS NOT NULL
   -- first
   OR b IS NOT NULL
   -- second (part 1)
   -- second (part 2)
   OR c > 0
;

-- Own-line comments before AND branches
SELECT
   a
FROM t
WHERE a > 1
  -- first
  AND b > 2
  -- second
  AND c IS NOT NULL -- trailing
;

-- Mixed AND / OR chain
SELECT
   a
FROM t
WHERE a > 1
  -- before and
  AND b > 2
   -- before or
   OR c = 3
;

-- A comment after the connector moves above it
SELECT
   a
FROM t
WHERE a = 1
   -- after the OR
   OR b = 2
;
