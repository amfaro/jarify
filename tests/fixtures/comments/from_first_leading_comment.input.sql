-- note about the first query
FROM people
;

SELECT 1 AS x
;

-- note about a later query
-- that takes two lines
FROM orders WHERE status = 'active'
;

WITH _active AS (FROM orders WHERE status = 'active')
-- note about the query after its WITH clause
FROM _active
;
