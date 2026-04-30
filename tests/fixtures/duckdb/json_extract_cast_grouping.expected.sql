SELECT
   (j->'x')::struct(a int)
  ,(j->>'label')::text
FROM t
;
