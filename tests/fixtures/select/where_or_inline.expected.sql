SELECT
   sku_key
FROM sku_catalog
WHERE supersedes IS NULL OR length(supersedes) = 0
;
