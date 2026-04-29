SELECT
   MAX(if(context = 'numerator', divisor, NULL)) AS numerator_divisor
  ,if(flag IS NULL, 'unknown', NULL)             AS flag_label
FROM t
;
