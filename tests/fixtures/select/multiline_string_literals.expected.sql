SELECT
   'a' || if(x = 1, 'one
two', 'b') AS v
  ,CASE
     WHEN x = 1
     THEN 'first line
second line'
     WHEN x = 2
     THEN 'c'
   END AS w
  ,STRING_AGG(name, ',
') AS names
  ,'note:
  indented as written' AS note
  ,id  AS id
FROM t
WHERE t.s != 'x
y'
GROUP BY ALL
;
