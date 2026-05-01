SELECT
   foo_bar_baz AS xyz
  ,CASE WHEN foo THEN bar WHEN baz AND baq THEN world ELSE null END AS abc
  ,CASE WHEN foo THEN bar WHEN baz OR hello THEN world ELSE null END AS def
FROM data
