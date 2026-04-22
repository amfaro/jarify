FROM people
;

FROM orders
WHERE status = 'active'
;

FROM products
ORDER BY
   name
;

FROM _actual, _target, _threshold
;
