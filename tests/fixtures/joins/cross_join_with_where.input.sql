SELECT a.x, b.y FROM a CROSS JOIN b WHERE a.id = b.id;
SELECT x FROM t1 CROSS JOIN t2 CROSS JOIN t3 WHERE t1.id = t2.id AND t2.id = t3.id;
SELECT a, b FROM t1, t2 WHERE t1.id = t2.id;
