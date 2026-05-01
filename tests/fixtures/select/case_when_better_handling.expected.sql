SELECT
   foo_bar_baz AS xyz
  ,CASE
     WHEN foo
     THEN bar
     WHEN baz
      AND baq
     THEN world
     ELSE NULL
   END        AS abc
  ,CASE
     WHEN foo
     THEN bar
     WHEN baz
       OR hello
     THEN world
     ELSE NULL
   END        AS def
FROM data
;
