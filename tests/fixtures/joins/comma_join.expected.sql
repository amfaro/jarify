SELECT
   a.id
  ,b.name
FROM a
CROSS JOIN b
;

SELECT
   x
FROM t1
CROSS JOIN t2
CROSS JOIN t3
WHERE t1.id = t2.fk
;
