SELECT
  MAX(CASE WHEN context = 'numerator' THEN divisor END) AS numerator_divisor
  , CASE WHEN flag IS NULL THEN 'unknown' END AS flag_label
FROM t
