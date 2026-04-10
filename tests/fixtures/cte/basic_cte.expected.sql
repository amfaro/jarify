WITH _base AS
(
  SELECT
     a
    ,b
  FROM foo
)
,_enriched AS
(
  SELECT
     _base.a
    ,bar.c
  FROM _base
  INNER JOIN bar
    ON _base.id = bar.id
)
SELECT
   _enriched.a
  ,_enriched.c
FROM _enriched
WHERE
  _enriched.a > 1
;
