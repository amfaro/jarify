SELECT
    program_key
  , list(group_by_value ORDER BY group_by_value) AS group_by_values
FROM _values
GROUP BY
    program_key
;
