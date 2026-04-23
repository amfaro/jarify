SELECT
   CASE x
    WHEN 'a' THEN (y, array_transform(ifnull(z, []::filter[]), f -> (f.a, f.b)::s))::mystruct::json
    WHEN 'b' THEN (y, array_transform(ifnull(z, []::filter[]), f -> (f.a, f.b)::s))::mystruct::json
  END AS result
FROM t
;
