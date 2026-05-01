MODEL (
  name foo.orders,
  kind FULL,
  dialect duckdb
);

SELECT
   order_id
  ,amount
FROM {{ ref('raw_orders') }}
WHERE ds BETWEEN @start_dt AND @end_dt
;
