SELECT
   x::decimal
  ,x::decimal
  ,x::decimal(10, 2)
  ,x::decimal(8, 4)
  ,(ir.rate_data->>'value')::decimal
FROM t
;
