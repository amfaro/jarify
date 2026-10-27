MODEL (
  name analytics.orders,
  kind FULL
);

SELECT order_id, amount FROM raw.orders WHERE amount > 0
;

-- FROM analytics.orders ORDER BY order_id LIMIT 100;

/*
  FROM analytics.orders
  WHERE order_id = @order_id
  LIMIT 1000
  ;
*/
