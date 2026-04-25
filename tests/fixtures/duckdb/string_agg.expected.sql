SELECT
   STRING_AGG(name, ', ' ORDER BY name) AS names
  ,STRING_AGG(tag, '-')                 AS tags
  ,STRING_AGG(code, ' | ')              AS codes
FROM t
;
