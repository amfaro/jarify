-- CASE WHEN condition with AND chain stays compact (no line breaks inside WHEN)
SELECT
   t.*
  ,s.sku_set
  ,CASE
     WHEN s.transform IS NOT NULL AND s.transform.type = 'coverage' THEN t.quantity/s.conversion_rate
     ELSE t.quantity
   END AS coverage
FROM transactions t
