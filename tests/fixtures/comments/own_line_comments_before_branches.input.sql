-- A comment on its own line after AND / OR moves above it
SELECT a FROM t
WHERE a > 1 AND
  -- why b
  b > 2 OR
  -- why c
  c = 3
;

-- The first branch inside parentheses keeps its comment on its own line
SELECT a FROM t
WHERE a > 1
  AND (
    -- either flag
    b = 1 OR c = 2
  )
;

-- Both: before the first condition and before a later one
SELECT a FROM t
WHERE
  -- first
  CAST(a AS int) = 1
  AND
  -- second
  (b = 1 OR c = 2)
;
