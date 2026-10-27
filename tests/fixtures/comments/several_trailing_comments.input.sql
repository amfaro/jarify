-- Comments written together after an argument stay on its line
SELECT
   coalesce(b, c, a /* first */ /* second */) AS v
  ,CAST(a /* first */ /* second */ AS int) AS w
  ,[1, 2 /* first */ /* second */] AS l
FROM t
WHERE x IN (1, 2 /* first */ /* second */)
GROUP BY ALL
;

-- Comments written on lines of their own before the semicolon aren't joined onto one line
SELECT
   a
FROM t
-- ORDER BY
--    a
;
