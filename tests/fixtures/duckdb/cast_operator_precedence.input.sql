SELECT
   CAST(a + b AS int) AS sum_cast
  ,CAST(a = b AS int) AS comparison_cast
  ,CAST(a BETWEEN 1 AND 2 AS int) AS between_cast
  ,CAST(a AND b AS int) AS conjunction_cast
  ,CAST(NOT a AS int) AS negation_cast
  ,CAST(-a AS text) AS minus_cast
  ,CAST(x IN (1, 2) AS int) AS in_cast
  ,CAST(s.f.g AS int) AS field_cast
  ,a::int + b AS cast_then_add
  ,-a::text AS minus_of_cast
FROM t
;
