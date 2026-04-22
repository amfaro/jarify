SELECT filter
FROM (SELECT UNNEST(_filters) AS filter)
WHERE filter.context = 'direct'
