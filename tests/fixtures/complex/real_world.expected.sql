SET VARIABLE tigris_bucket = getenv('TIGRIS_BUCKET')
;

SET VARIABLE time_frame = getenv('TIME_FRAME')
;

WITH _latest_version AS
(
  SELECT
     regexp_extract(file, 'version=(.{21})', 1) AS version
  FROM glob('s3://' || getvariable('tigris_bucket') || '/global-catalog/*/*')
  ORDER BY
     file DESC
  LIMIT 1
)
,_relevant_skus AS
(
  FROM read_parquet(
     's3://' || getvariable('tigris_bucket') || '/dataops/*/*/relevant_skus.parquet'
    ,hive_partitioning = TRUE
    ,hive_types = {'program_supplier_key': text, 'time_frame': int}
  )
  WHERE time_frame = getvariable('time_frame')
)
,_enrollments AS
(
  FROM read_parquet(
     's3://' || getvariable('tigris_bucket') || '/dataops/*/*/enrollments.parquet'
    ,hive_partitioning = TRUE
    ,hive_types = {'program_supplier_key': text, 'time_frame': int}
  )
  WHERE time_frame = getvariable('time_frame')
)
,_sku_catalog AS
(
  SELECT
     *
  FROM read_parquet(
     's3://' || getvariable('tigris_bucket') || '/global-catalog/*/sku_catalog.parquet'
    ,hive_partitioning = TRUE
    ,hive_types = {'version': text}
  )
  SEMI JOIN _latest_version
    USING (version)
)
,_prices AS
(
  SELECT
     *
  FROM read_parquet(
     's3://' || getvariable('tigris_bucket') || '/global-catalog/*/prices.parquet'
    ,hive_partitioning = TRUE
    ,hive_types = {'version': text}
  )
  SEMI JOIN _latest_version
    USING (version)
)
SELECT
   sc.manufacturer_label
  ,sc.brand_prefix_label
  ,sc.pack_size_label
  ,sc.sku_key
  ,p.program_redemption_price
  ,p.origin
  ,all_e.participant_key
  ,CASE WHEN e.participant_key IS NOT NULL THEN 'Y' ELSE 'N' END AS enrolled
  ,sc.version
FROM _relevant_skus AS rs
INNER JOIN _sku_catalog AS sc
  ON sc.sku_key = rs.sku_key
  AND sc.manufacturer_key = rs.program_supplier_key
CROSS JOIN (
  SELECT DISTINCT
     participant_key
  FROM _enrollments
) AS all_e
LEFT JOIN _enrollments AS e
  ON e.participant_key = all_e.participant_key
  AND e.program_supplier_key = rs.program_supplier_key
  AND e.enabled = TRUE
LEFT JOIN _prices AS p
  ON sc.version = p.version
  AND sc.sku_key = p.sku_key
  AND p.end_date IS NULL
ORDER BY
   manufacturer_label
  ,sku_key
;
