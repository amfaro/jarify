WITH _base AS (SELECT 1)
-- materialize for reuse below
,_hot AS MATERIALIZED (SELECT * FROM _base)
SELECT * FROM _hot;
