SELECT
   o.*
FROM offers o
CROSS JOIN UNNEST(o.group_by_values) gbv(group_by_value)
;
