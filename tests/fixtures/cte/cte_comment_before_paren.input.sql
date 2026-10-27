-- A comment between AS and the opening paren goes after AS
WITH _a AS
-- note
(SELECT 1 AS x)
SELECT x FROM _a
;

WITH _a AS (SELECT 1 AS x)
,_b AS MATERIALIZED
-- reused below
(SELECT x FROM _a)
,_c AS NOT MATERIALIZED /* inline */ (SELECT x FROM _b)
SELECT x FROM _c
;

-- Several comments go above the CTE, one per line
WITH _a AS -- first
-- second
(SELECT 1 AS x)
SELECT x FROM _a
;
