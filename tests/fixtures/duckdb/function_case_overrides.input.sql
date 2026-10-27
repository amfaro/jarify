SELECT
  string_agg(a, ',') AS s,
  listagg(b, ', ') AS la,
  any_value(c) AS v,
  List(d) AS l,
  array_agg(e ORDER BY e) AS ae,
  arg_max(f, g) AS am,
  lag(h) OVER (ORDER BY i) AS lg,
  regexp_extract(j, '[0-9]+') AS r,
  IFNULL(k, 0) AS ik,
  coalesce(m, 0) AS im,
  CASE WHEN n THEN 1 ELSE 0 END AS cw,
  my_macro(o) AS mm,
  other_macro(p) AS om,
  main.my_macro(q) AS qm
FROM t
