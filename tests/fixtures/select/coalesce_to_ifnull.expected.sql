SELECT
   ifnull(a, b)      AS two_arg
  ,ifnull(c, d)      AS two_arg_upper
  ,coalesce(a, b, c) AS three_arg
FROM t
;
