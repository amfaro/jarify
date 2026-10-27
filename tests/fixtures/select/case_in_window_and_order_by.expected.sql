-- A CASE in a window's ORDER BY or PARTITION BY wraps the window, one key per line
SELECT
   ROW_NUMBER() OVER (
     PARTITION BY a
     ORDER BY
        CASE
          WHEN x = 1
          THEN 'one'
          WHEN x = 2
          THEN 'two'
          ELSE 'many'
        END
  ) AS n
  ,SUM(v) OVER (
     PARTITION BY
        CASE k
         WHEN 1 THEN 'one'
         ELSE 'other'
       END
       ,b
     ORDER BY c DESC
  ) AS running
FROM t
;

-- A CASE in an aggregate's ORDER BY or argument puts ORDER BY on its own line
SELECT
   list(
     x
     ORDER BY
        CASE
          WHEN x = 1
          THEN 'one'
          WHEN x = 2
          THEN 'two'
          ELSE 'many'
        END
  ) AS by_case
  ,list(
     CASE
       WHEN x = 1
       THEN 'one'
       WHEN x = 2
       THEN 'two'
       ELSE 'many'
     END
     ORDER BY y
  ) AS of_case
FROM t
GROUP BY ALL
;
