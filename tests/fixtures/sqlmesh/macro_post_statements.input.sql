MODEL (
  name foo.macro_orders,
  kind FULL,
  dialect duckdb
);

@DEF(
  amount_cols,
  [amount, tax]  -- keep in sync with the source )
);
@DEF(min_amount, 0);

select order_id,@amount_cols from @read_parquet(@source_db, 'orders') where amount > @min_amount;

-- Post-statements run after the query.
@grant_select('analysts');
@IF(
  @runtime_stage = 'evaluating',
  CREATE INDEX IF NOT EXISTS orders_idx ON @this_model (order_id)
);
-- End of model.
