SELECT
   o.id
  ,c.name
  ,s.status
  ,p.amount
  ,r.rate
  ,w.note
FROM orders                     o
INNER JOIN customers            c ON c.id = o.customer_id
LEFT OUTER JOIN shipments       s ON s.order_id = o.id
RIGHT OUTER JOIN payments       p ON p.order_id = o.id
FULL OUTER JOIN refunds        rf ON rf.order_id = o.id
ASOF LEFT OUTER JOIN fx_rates   r ON r.currency = o.currency AND r.valid_from <= o.created_at
LEFT OUTER JOIN warehouse_notes w ON w.order_id = o.id
;
