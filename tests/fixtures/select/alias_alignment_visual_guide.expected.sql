-- jarify: set alias-visual-guide-interval = 12
SELECT
   customer_name       AS name
  ,id                  AS customer_id
FROM customers
;

SELECT
   lifetime_orders_cnt AS order_count
  ,id                  AS customer_id
FROM customer_stats
;

SELECT
   c.id                            AS customer_id
  ,CASE
     WHEN c.lifetime_value_cents > 100000
     THEN 'gold'
     WHEN c.lifetime_value_cents > 10000
     THEN 'silver'
     ELSE 'bronze'
   END                             AS tier
  ,c.lifetime_value_cents / 100.0  AS lifetime_value
FROM customers c
;
