SELECT
  'prefix: ' || group_field || string_agg(transaction_id, ', ') || group_key
FROM t
GROUP BY group_field, group_key
;
