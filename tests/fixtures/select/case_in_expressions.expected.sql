-- A CASE in parentheses keeps them around it
SELECT
   (CASE
      WHEN x = 1
      THEN 'one'
      WHEN x = 2
      THEN 'two'
      ELSE 'many'
    END) || 'x' AS concatenated
  ,(CASE
      WHEN x = 1
      THEN 'one'
      WHEN x = 2
      THEN 'two'
      ELSE 'many'
    END)::text  AS cast_text
  ,(
    a + CASE
          WHEN x = 1
          THEN 1
          WHEN x = 2
          THEN 2
          ELSE 3
        END
  ) * 2         AS doubled
FROM t
;

-- A CASE after an operator is laid out under its CASE keyword
SELECT
   a        AS kept
  ,b || CASE
          WHEN x = 1
          THEN 'one'
          WHEN x = 2
          THEN 'two'
          ELSE 'many'
        END AS suffixed
  ,1 + CASE k
        WHEN 1 THEN 10
        WHEN 2 THEN 20
        ELSE 30
      END   AS added
FROM t
;

-- string_agg() puts its arguments on their own lines, like sum() or list()
SELECT
   STRING_AGG(
     CASE
       WHEN x = 1
       THEN 'one'
       WHEN x = 2
       THEN 'two'
       ELSE 'many'
     END
    ,', '
  ) AS joined
  ,STRING_AGG(
     CASE
       WHEN x = 1
       THEN 'one'
       WHEN x = 2
       THEN 'two'
       ELSE 'many'
     END
    ,', '
     ORDER BY y DESC
  ) AS ordered
  ,COUNT(
     DISTINCT CASE
                WHEN x = 1
                THEN 'one'
                WHEN x = 2
                THEN 'two'
                ELSE 'many'
              END
  ) AS distinct_count
FROM t
GROUP BY ALL
;

-- An IN list or a list literal holding a CASE puts one value per line
SELECT
   x IN (
     'none'
    ,CASE
       WHEN y = 1
       THEN 'one'
       WHEN y = 2
       THEN 'two'
       ELSE 'many'
     END
  ) AS matched
  ,[
     0
    ,CASE
       WHEN y = 1
       THEN 1
       WHEN y = 2
       THEN 2
       ELSE 3
     END
  ] AS numbers
FROM t
;
