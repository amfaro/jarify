FROM people
;

FROM orders
WHERE status = 'active'
;

FROM products
ORDER BY
   name
;

SELECT
   *
FROM _actual
CROSS JOIN _target
CROSS JOIN _threshold
;
