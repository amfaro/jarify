SELECT
   t.id
FROM df
INNER JOIN t
WHERE list_contains(df.filter.sku_keys::text[], t.sku_key)
;
