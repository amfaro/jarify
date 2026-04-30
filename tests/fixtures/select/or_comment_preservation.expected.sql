FROM t
WHERE 1 = 1
  AND (
    -- No prior-year baseline: infinite YoY improvement → highest tier
    (t.qualification_met AND t.qualification_target = 0)
    OR t.threshold_value >= r.threshold
  )
;
