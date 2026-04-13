FROM people
;

FROM orders
WHERE status = 'active'
;

FROM products
ORDER BY
   name
;
