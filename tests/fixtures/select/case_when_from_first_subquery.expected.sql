/* CASE THEN values containing SELECT * FROM subqueries stay compact */
SELECT
   CASE _op
    WHEN 'variants' THEN (SELECT * FROM (SELECT unnest(_variants) AS variant))
    WHEN 'filters'  THEN (SELECT * FROM (SELECT unnest(_filters) AS filter))
  END AS result
FROM t
;
