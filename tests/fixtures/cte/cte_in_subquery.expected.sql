-- A subquery holding a WITH is laid out with its CTEs as at the top level
SELECT
   s.a
FROM (
  WITH c AS -- note c
  (
    SELECT
       1 AS a
  )
  SELECT
     a
  FROM c
) AS s
WHERE s.a IN
(
  WITH d AS
  (
    SELECT
       1 AS a
  )
  SELECT
     a
  FROM d
)
;

-- Its comments survive a statement rendered twice to align aliases
SELECT
   (
    WITH c AS -- note c
    (
      SELECT
         1 AS a
    )
    SELECT
       MAX(a)
    FROM c
  )  AS m
  ,1 AS n
FROM t
;
