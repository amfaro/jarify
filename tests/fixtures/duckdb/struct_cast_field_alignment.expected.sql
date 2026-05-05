SELECT
   sku_key
  ,list((
     key
    ,'string'
    ,value
  )::struct(key text, type text, value text)) AS external_ids
FROM sku_external_ids
GROUP BY ALL
;
