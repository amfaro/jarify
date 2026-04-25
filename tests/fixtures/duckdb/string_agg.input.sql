SELECT
  string_agg(name, ', ' ORDER BY name) AS names,
  string_agg(tag, '-') AS tags,
  listagg(code, ' | ') AS codes
FROM t
