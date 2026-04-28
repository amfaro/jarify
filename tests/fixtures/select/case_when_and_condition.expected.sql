-- CASE WHEN condition with AND chain stays compact (no line breaks inside WHEN)
SELECT
   t.*
  ,s.sku_set
  ,if(s.transform IS NOT NULL AND s.transform.type = 'coverage', t.quantity / s.conversion_rate, t.quantity) AS coverage
FROM transactions t
;
