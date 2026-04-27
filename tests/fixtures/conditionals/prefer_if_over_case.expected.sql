SELECT
   a
  ,if(a > 1, 'big', 'small') AS size
  ,if(b IS NULL, 0) AS b_or_zero
  ,if(status = 'active', 1, 0) AS is_active
  ,CASE
    WHEN a = 1 THEN 'one'
    WHEN a = 2 THEN 'two'
    ELSE 'other'
  END AS label
  ,CASE a
    WHEN 1 THEN 'one'
    ELSE 'other'
  END AS simple_case
FROM t
;
