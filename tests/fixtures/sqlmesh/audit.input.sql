AUDIT (
  name assert_positive_amount,
  dialect duckdb
);

select * from orders where amount < 0
