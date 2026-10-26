-- Trailing comments on OR branches, including IS NOT NULL and a parenthesized branch
WITH _eligible AS (
  SELECT h.user_id
  FROM _hierarchy h
  WHERE a.allocation_per_year IS NOT NULL --eligible_for_allocation = 1
     OR nr.nominee_user_id IS NOT NULL     --has_points_spend = 1
     OR (h.rollup_level_id = 0 AND te.user_id IS NOT NULL)  --manager whose team is eligible
)
SELECT user_id FROM _eligible;

-- Trailing comments on AND branches
SELECT a FROM t
WHERE a IS NOT NULL -- first
  AND b IS NULL -- second
  AND c = 1 -- third
;

-- Single commented condition
SELECT a FROM t WHERE a IS NOT NULL -- only
;

-- Trailing comment inside a parenthesized group keeps the OR on its own line
SELECT a FROM t
WHERE a = 1
  AND ((b = 2) -- b branch
       OR c IS NOT NULL -- c branch (see 1)
      )
;
