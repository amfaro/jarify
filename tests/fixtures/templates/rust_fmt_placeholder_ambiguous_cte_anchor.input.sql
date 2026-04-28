WITH _sku_catalog AS
(
  SELECT *
  FROM sku_catalog
)
,_aggregated_and_sorted AS
(
  SELECT array_agg((f) ORDER BY key) AS skus
  FROM _final f
  {manufacturer_filter}
)
SELECT skus::json AS skus
FROM _aggregated_and_sorted
;
