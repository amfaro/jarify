CREATE OR REPLACE MACRO aggregated_amount_qualification
(
   _scope
  ,_level_key
  ,_operator
  ,_level_type
  ,_value
  ,_filters
  ,_transform
  ,_variants
) AS TABLE
(
  WITH _direct_filters AS
  (
    SELECT
       filter
    FROM (
      SELECT
         unnest(_filters) AS filter
    )
    WHERE filter.context = 'direct'
  )
  FROM _direct_filters
)
;
