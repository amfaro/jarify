AUDIT (
  name assert_positive_amount,
  dialect duckdb
);

FROM orders
WHERE amount < 0
;
