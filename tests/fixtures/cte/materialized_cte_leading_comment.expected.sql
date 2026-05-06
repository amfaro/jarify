WITH _base AS
(
  SELECT
     1
)
-- materialize for reuse below
,_hot AS MATERIALIZED
(
  FROM _base
)
FROM _hot
;
