SELECT
   sku_key
  ,array_agg((key, 'string', value)::STRUCT(key text, type text, value text)) AS external_ids
FROM sku_external_ids
GROUP BY ALL
;
