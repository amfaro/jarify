SELECT
   f.a
  ,b.b
  ,q.c
FROM foo          f
INNER JOIN barbaz b ON b.id = f.id
INNER JOIN q ON q.id = f.id
LEFT JOIN cc      c ON c.id = f.id
;
