WITH _shipments AS
(
  SELECT
     s.order_id
    ,s.status
  FROM shipments           s
  LEFT OUTER JOIN carriers c USING (carrier_id)
  RIGHT OUTER JOIN regions r ON r.id = c.region_id
)
SELECT
   o.id
  ,sh.status
  ,t.tag
FROM (SELECT orders.id FROM orders LEFT OUTER JOIN holds ON holds.order_id = orders.id) AS o
LEFT OUTER JOIN _shipments sh ON sh.order_id = o.id
LEFT OUTER JOIN UNNEST(['a', 'b']) t(tag) ON true
;
