WITH base AS
(
  SELECT
     a
    ,b
  FROM foo
)
,enriched AS
(
  SELECT
     base.a
    ,bar.c
  FROM base
  INNER JOIN bar
    ON base.id = bar.id
)
SELECT
   enriched.a
  ,enriched.c
FROM enriched
WHERE
  enriched.a > 1;
