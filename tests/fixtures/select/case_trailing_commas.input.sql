-- With trailing commas, a CASE is laid out under its CASE keyword too
SELECT
  a,
  CASE WHEN x = 1 THEN 'one' WHEN x = 2 THEN 'two' ELSE 'many' END AS searched,
  CASE k WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'many' END AS simple,
  CASE WHEN y = 1 THEN CASE WHEN x = 1 THEN 'one' WHEN x = 2 THEN 'two' END WHEN y = 2 THEN 'b' END AS nested,
  b
FROM t
WHERE CASE WHEN x = 1 THEN 'one' WHEN x = 2 THEN 'two' ELSE 'many' END = 'one'
ORDER BY CASE k WHEN 1 THEN 'one' ELSE 'many' END, b
;
