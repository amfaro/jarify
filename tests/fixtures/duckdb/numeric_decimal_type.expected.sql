SELECT
   x::numeric
  ,x::decimal
  ,x::decimal(10, 2)
  ,x::numeric(8, 4)
  ,(ir.rate_data->>'value')::numeric
FROM t
;
