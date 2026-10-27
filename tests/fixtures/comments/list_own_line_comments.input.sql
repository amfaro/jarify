-- An own-line comment before a list item lines up with the commas
SELECT a FROM t
WHERE b IN (
  1,
  -- note
  2
)
;

SELECT
  a,
  -- note
  b
FROM t
;

SELECT a FROM t
WHERE x = 1
  AND b IN (
    -- first
    1,
    -- second
    2
  )
;
