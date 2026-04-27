SELECT
   o.id
  ,u.name
  ,a.city
FROM orders          o
LEFT JOIN users      u ON u.id = o.user_id
LEFT JOIN addresses  a ON a.id = o.shipping_address_id
LEFT JOIN line_items li ON li.order_id = o.id
LEFT JOIN products   p ON p.id = li.product_id
;
