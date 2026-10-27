-- WHERE, HAVING and QUALIFY lay a CASE out under its CASE keyword
SELECT
   a
FROM t
WHERE CASE
        WHEN x = 1
        THEN 'one'
        WHEN x = 2
        THEN 'two'
        ELSE 'many'
      END = 'one'
  AND b = CASE k
           WHEN 1 THEN 'one'
           WHEN 2 THEN 'two'
         END
  AND c = 3
  AND (
    d = 1 OR CASE
               WHEN x = 1
               THEN true
               WHEN x = 2
               THEN false
             END
  )
;

SELECT
   a
FROM t
WHERE a = 1
   OR CASE
        WHEN x = 1
        THEN 'one'
        WHEN x = 2
        THEN 'two'
        ELSE 'many'
      END = 'one'
;

SELECT
   a
  ,COUNT(*) AS n
FROM t
GROUP BY ALL
HAVING CASE
         WHEN a = 1
         THEN 'one'
         WHEN a = 2
         THEN 'two'
         ELSE 'many'
       END = 'one'
QUALIFY
  CASE
    WHEN n = 1
    THEN 'one'
    WHEN n = 2
    THEN 'two'
    ELSE 'many'
  END = 'one'
;

-- A JOIN ... ON holding a CASE is laid out like WHERE
SELECT
   t.a
FROM t
INNER JOIN u ON u.k = CASE
                        WHEN t.x = 1
                        THEN 'one'
                        WHEN t.x = 2
                        THEN 'two'
                        ELSE 'many'
                      END
            AND u.j = t.j
;

-- A subquery or a FILTER holding a CASE isn't put on one line
SELECT
   a
FROM t
WHERE a IN
(
  SELECT
     CASE
       WHEN x = 1
       THEN 'one'
       WHEN x = 2
       THEN 'two'
     END
  FROM u
)
;

FROM (
  SELECT
     CASE
       WHEN x = 1
       THEN 'one'
       WHEN x = 2
       THEN 'two'
     END AS a
  FROM u
)
;

SELECT
   COUNT(*) FILTER(WHERE CASE
                           WHEN x = 1
                           THEN 'one'
                           WHEN x = 2
                           THEN 'two'
                         END = 'one') AS ones
FROM t
;
