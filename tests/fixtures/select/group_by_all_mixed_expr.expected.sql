SELECT
   'prefix: ' || group_field || STRING_AGG(transaction_id, ', ') || group_key
FROM t
GROUP BY
   group_field
  ,group_key
;
