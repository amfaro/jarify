SELECT
   foo
  ,array_transform(
     list_filter(si.filters, lambda f: f.context = 'direct' OR f.context IS NULL)
    ,lambda f: (
       f.period.period_key
      ,f.sku_keys
      ,f.transaction_type
    )::filter_struct
  ) AS filters
;
