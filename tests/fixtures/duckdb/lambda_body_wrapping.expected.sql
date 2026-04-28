SELECT
   list_transform(
     a
    ,x -> {
       'key': x.key
      ,'period_key': x.period_key
      ,'transaction_type': x.transaction_type
      ,'conversion': {'coverage_unit': x.conversion.coverage_unit}::conversion_struct
      ,'rates': list_transform(x.rates, r -> {'sku_key': r.sku_key, 'rate': r.value, 'measure': r.measure}::rate_struct)
    }::my_struct
  ) AS result
;
