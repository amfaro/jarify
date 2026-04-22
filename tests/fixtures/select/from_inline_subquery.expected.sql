SELECT
   filter
FROM (SELECT unnest(_filters) AS filter)
WHERE filter.context = 'direct'
;
