MODEL (
  name foo.pre_post_orders,
  kind FULL,
  dialect duckdb
);

CREATE OR REPLACE TEMPORARY TABLE _jarify_stage_orders AS
SELECT
   order_id
  ,amount
  ,ds
FROM @input_model
WHERE ds = @run_dt
;

SELECT
   order_id
  ,amount
FROM _jarify_stage_orders
WHERE amount > 0
;

DROP TABLE IF EXISTS _jarify_stage_orders
;
