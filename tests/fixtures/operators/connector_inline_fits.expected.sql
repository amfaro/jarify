SELECT
   foo
  ,array_transform(
     list_filter(si.filters, f -> f.context = 'direct' OR f.context IS NULL)
    ,f -> (
       f.period.period_key
      ,f.sku_keys
      ,f.transaction_type
    )::filter_struct
  ) AS filters
;
