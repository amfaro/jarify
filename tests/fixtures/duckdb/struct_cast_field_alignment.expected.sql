SELECT
   sku_key
  ,ARRAY_AGG((
     key
    ,'string'
    ,value
  )::struct(key text, type text, value text)) AS external_ids
FROM sku_external_ids
GROUP BY ALL
;
