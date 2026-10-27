SELECT
   (a + b)::int             AS sum_cast
  ,(a = b)::int             AS comparison_cast
  ,(a BETWEEN 1 AND 2)::int AS between_cast
  ,(a AND b)::int           AS conjunction_cast
  ,(NOT a)::int             AS negation_cast
  ,(-a)::text               AS minus_cast
  ,(x IN (1, 2))::int       AS in_cast
  ,s.f.g::int               AS field_cast
  ,a::int + b               AS cast_then_add
  ,-a::text                 AS minus_of_cast
FROM t
;
