SELECT
   coalesce(a, b)    AS two_arg
  ,COALESCE(c, d)    AS two_arg_upper
  ,coalesce(a, b, c) AS three_arg
FROM t
