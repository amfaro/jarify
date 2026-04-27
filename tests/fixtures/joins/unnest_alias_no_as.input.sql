SELECT
   o.*
FROM offers AS o
CROSS JOIN UNNEST(o.group_by_values) AS gbv(group_by_value)
;
