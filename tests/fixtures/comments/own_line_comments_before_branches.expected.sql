-- A comment on its own line after AND / OR moves above it
SELECT
   a
FROM t
WHERE a > 1
  -- why b
  AND b > 2
   -- why c
   OR c = 3
;

-- The first branch inside parentheses keeps its comment on its own line
SELECT
   a
FROM t
WHERE a > 1
  AND (
    -- either flag
    b = 1
    OR c = 2
  )
;

-- Both: before the first condition and before a later one
SELECT
   a
FROM t
-- first
WHERE a::int = 1
  -- second
  AND (b = 1 OR c = 2)
;
