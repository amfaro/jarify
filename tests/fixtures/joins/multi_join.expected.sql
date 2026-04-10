SELECT
   a
FROM foo
LEFT JOIN bar
  ON foo.id = bar.id
INNER JOIN baz
  ON baz.id = foo.id
;
