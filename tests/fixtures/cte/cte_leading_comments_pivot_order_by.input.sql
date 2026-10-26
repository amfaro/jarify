WITH _d AS (SELECT a, grp, val FROM t)
-- first line about _e
-- second line about _e
,_e AS (SELECT a, grp, val FROM _d)
PIVOT _e ON grp USING first(val) ORDER BY a;
