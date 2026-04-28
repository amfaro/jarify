SELECT
   list_transform(
     incentive -> 'sku_sets'::struct(
      key text
      , period_key text
      , product_supplier text
      , transaction_type text
      , conversion struct(coverage_unit text, rates struct(sku_key text, value double, "from" text)[])
     )[]
    ,x -> x.key
  ) AS sku_sets
;
