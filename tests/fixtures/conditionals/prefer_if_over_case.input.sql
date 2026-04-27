SELECT
  a
  , CASE WHEN a > 1 THEN 'big' ELSE 'small' END AS size
  , CASE WHEN b IS NULL THEN 0 END AS b_or_zero
  , CASE WHEN status = 'active' THEN 1 ELSE 0 END AS is_active
  , CASE
      WHEN a = 1 THEN 'one'
      WHEN a = 2 THEN 'two'
      ELSE 'other'
    END AS label
  , CASE a WHEN 1 THEN 'one' ELSE 'other' END AS simple_case
FROM t
