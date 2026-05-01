MODEL (
  name foo.orders,
  kind FULL,
  dialect duckdb
);

select order_id,amount from {{ ref('raw_orders') }} where ds between @start_dt and @end_dt
