-- A subquery holding a WITH is laid out with its CTEs as at the top level
-- wherever it appears, as a subquery too long for one line would be:
-- in a parenthesized condition
SELECT
   a
FROM t
WHERE (
  a IN
  (
    WITH c AS
    (
      SELECT
         1 AS a
    )
    SELECT
       a
    FROM c
  )
  OR b
)
;

-- after AND, and in an OR chain
SELECT
   a
FROM t
WHERE x = 1
  AND (
    a IN
    (
      WITH c AS
      (
        SELECT
           1 AS a
      )
      SELECT
         a
      FROM c
    )
    OR b
  )
;

SELECT
   a
FROM t
WHERE a IN
(
  WITH c AS
  (
    SELECT
       1 AS a
  )
  SELECT
     a
  FROM c
)
   OR b
;

-- in HAVING
SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
HAVING COUNT(*) > (
  WITH c AS
  (
    SELECT
       1 AS a
  )
  SELECT
     MAX(a)
  FROM c
)
    OR a = 1
;

-- in a JOIN condition
SELECT
   t.a
FROM t
INNER JOIN u ON u.id = t.id
            AND u.a IN
            (
              WITH c AS
              (
                SELECT
                   1 AS a
              )
              SELECT
                 a
              FROM c
            )
;

-- as an if() argument
SELECT
   if(
      x
     ,(
        WITH c AS
        (
          SELECT
             1 AS a
        )
        SELECT
           MAX(a)
        FROM c
      )
     ,0
  ) AS v
FROM t
;

-- in a CASE condition, and as a simple CASE's WHEN value
SELECT
   CASE
     WHEN a > (
       WITH c AS
       (
         SELECT
            1 AS a
       )
       SELECT
          MAX(a)
       FROM c
     )
     THEN 1
     WHEN b
     THEN 2
   END AS v
  ,CASE x
    WHEN (
      WITH c AS
      (
        SELECT
           1 AS a
      )
      SELECT
         MAX(a)
      FROM c
    ) THEN 1
    WHEN 2 THEN 3
  END  AS w
FROM t
;

-- in parentheses in a SELECT list, and in a CTE body
WITH _d AS
(
  SELECT
     a
    ,(
      a IN
      (
        WITH c AS
        (
          SELECT
             1 AS a
        )
        SELECT
           a
        FROM c
      )
      OR b
    ) AS v
  FROM t
)
SELECT
   a
  ,v
FROM _d
;
