SELECT DISTINCT
   t.sku_key
FROM read_arrow(?, ?) t
LEFT JOIN sku_catalog sc ON sc.sku_key = t.sku_key
WHERE sc.sku_key IS NULL
;
