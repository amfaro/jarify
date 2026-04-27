SELECT
   a
  ,b
  ,SUM(c) AS total
FROM t
GROUP BY ALL
;
