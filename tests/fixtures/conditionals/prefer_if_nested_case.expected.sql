SELECT
   if(x, 1, if(c, 4, 5))                    AS in_else
  ,if(x, if(c, 4, 5), 0)                    AS in_then
  ,if(x, if(c, if(d, 6, NULL), NULL), NULL) AS three_deep
  ,CASE
     WHEN a = 1
     THEN if(b, 'b', 'not b')
     WHEN a = 2
     THEN 'two'
     ELSE if(c, 'c', NULL)
   END                                      AS in_multi_when
FROM t
;
