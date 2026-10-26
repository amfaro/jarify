-- jarify: set alias-visual-guide-interval = 12
-- jarify: set min-column-alias = 34
SELECT
   id                              AS order_id
  ,status                          AS order_status
FROM orders
;

SELECT
   id                                          AS order_id
  ,ifnull(shipping_address, billing_address)   AS address
FROM orders
;

WITH _order_totals AS
(
  WITH _line_items AS
  (
    SELECT
       order_id                                            AS order_id
      ,quantity * unit_price_cents * (1 - discount_rate)   AS line_total_cents
    FROM order_lines
  )
  SELECT
     order_id                                              AS order_id
    ,SUM(line_total_cents)                                 AS total_cents
  FROM _line_items
  GROUP BY ALL
)
SELECT
   o.id                                                    AS order_id
  ,t.total_cents                                           AS total_cents
FROM orders              o
INNER JOIN _order_totals t ON t.order_id = o.id
;
