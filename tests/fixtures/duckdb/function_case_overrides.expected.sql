SELECT
   string_agg(a, ',')          AS s
  ,string_agg(b, ', ')         AS la
  ,any_value(c)                AS v
  ,LIST(d)                     AS l
  ,LIST(e ORDER BY e)          AS ae
  ,ARG_MAX(f, g)               AS am
  ,lag(h) OVER (ORDER BY i)    AS lg
  ,regexp_extract(j, '[0-9]+') AS r
  ,IFNULL(k, 0)                AS ik
  ,IFNULL(m, 0)                AS im
  ,IF(n, 1, 0)                 AS cw
  ,MY_MACRO(o)                 AS mm
  ,other_macro(p)              AS om
  ,main.my_macro(q)            AS qm
FROM t
;
